import os
import re
import subprocess
import requests
import sqlite3
import psutil 
import json
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable
import config

class WorkerSignals(QObject):
    finished = pyqtSignal(object)

class AutocompleteSearcher(QRunnable):
    def __init__(self, search_text):
        super().__init__()
        self.search_text = search_text
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        conn = None
        try:
            conn = sqlite3.connect(config.DB_PATH)
            cursor = conn.cursor()
            
            query = "SELECT name FROM games WHERE name LIKE ? ORDER BY name LIMIT 15"
            pattern = f'%{self.search_text}%'
            
            cursor.execute(query, (pattern,))
            results = cursor.fetchall()
            
            flat_results = [row[0] for row in results]
            self.signals.finished.emit(flat_results)
            
        except sqlite3.Error as e:
            print(f"Erro no worker de autocompletar: {e}")
            self.signals.finished.emit([])
        finally:
            if conn:
                conn.close()

class ManualSyncWorker(QRunnable):
    def __init__(self, game_data, signals, config_dir, mode='--sync-now'):
        super().__init__()
        self.game_data = game_data
        self.signals = signals
        self.config_dir = config_dir
        self.mode = mode

    @pyqtSlot()
    def run(self):
        full_log_output = f"--- Sincronizacao On-Demand ({self.mode}) para: {self.game_data['name']} ---\n\n"
        try:
            save_path = self.game_data.get('save_path', '')
            if not os.path.isdir(save_path): 
                raise FileNotFoundError(f"Pasta de save nao encontrada: '{save_path}'")
            
            files_in_dir = [f for f in os.listdir(save_path) if not f.endswith('.bak') and os.path.isfile(os.path.join(save_path, f))]
            if not files_in_dir:
                full_log_output += "Nenhum arquivo de save encontrado na pasta para sincronizar.\n"

            for filename in files_in_dir:
                full_save_path = os.path.join(save_path, filename)
                sanitized_folder = re.sub(r'[™®©:/\\?*|"<>]+', '', self.game_data['name']).strip()
                remote_name = f"{sanitized_folder}/{filename}"
                
                command = [
                    config.EXE_PATH, 
                    self.mode, 
                    "--localpath", full_save_path, 
                    "--remotename", remote_name, 
                    "--configdir", self.config_dir
                ]
                
                full_log_output += f"Executando para '{filename}': {' '.join(command)}\n"
                result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, encoding='utf-8', errors='replace')
                
                if result.stdout: full_log_output += f"Saida de '{filename}':\n{result.stdout}\n"
                if result.stderr: full_log_output += f"Erros de '{filename}':\n{result.stderr}\n"
                if result.returncode != 0: 
                    raise RuntimeError(f"Processo de sincronizacao para '{filename}' retornou um erro.")

            self.signals.finished.emit({"success": True, "game_data": self.game_data, "log": full_log_output})
        
        except Exception as e:
            full_log_output += f"\nERRO CRITICO:\n{e}\n"
            self.signals.finished.emit({"success": False, "message": str(e), "game_data": self.game_data, "log": full_log_output})

class ImageDownloader(QRunnable):
    def __init__(self, appid, save_path, signals):
        super().__init__()
        self.appid = appid
        self.save_path = save_path
        self.signals = signals
    @pyqtSlot()
    def run(self):
        result = None
        try:
            url = f"https://cdn.akamai.steamstatic.com/steam/apps/{self.appid}/library_600x900.jpg"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(self.save_path, 'wb') as f: f.write(response.content)
                result = self.save_path
        except requests.exceptions.RequestException as e:
            print(f"Erro ao baixar imagem: {e}")
        self.signals.finished.emit(result)

class RemoteFileListerWorker(QRunnable):
    def __init__(self, game_folder_name, signals):
        super().__init__()
        self.game_folder_name = game_folder_name
        self.signals = signals
    @pyqtSlot()
    def run(self):
        try:
            command = [config.DELETER_EXE_PATH, "--list-remote", self.game_folder_name]
            result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, encoding='utf-8', errors='replace')
            if result.returncode != 0:
                raise RuntimeError(f"Falha ao listar arquivos. Stderr: {result.stderr}")
            remote_files_data = json.loads(result.stdout)
            self.signals.finished.emit({"success": True, "files": remote_files_data})
        except Exception as e:
            self.signals.finished.emit({"success": False, "message": str(e)})

class SaveDeleterWorker(QRunnable):
    def __init__(self, files_to_delete, signals):
        super().__init__()
        self.files_to_delete = files_to_delete
        self.signals = signals
    @pyqtSlot()
    def run(self):
        log = ""
        try:
            if not self.files_to_delete:
                raise ValueError("Nenhum arquivo especificado para delecao.")
            
            if not os.path.exists(config.DELETER_EXE_PATH):
                raise FileNotFoundError(f"Executavel de delecao nao encontrado em: {config.DELETER_EXE_PATH}")

            command = [config.DELETER_EXE_PATH] + self.files_to_delete
            log += f"Comando a ser executado:\n{' '.join(command)}\n\n"
            
            result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, encoding='utf-8', errors='replace')
            
            log += f"Saida (stdout):\n{result.stdout}\n"
            log += f"Erros (stderr):\n{result.stderr}\n"
            
            if "ERRO" in result.stdout.upper() or "FALHA AO CONECTAR" in result.stdout.upper():
                raise RuntimeError(f"O deleter.exe retornou um erro critico.\n\n{result.stderr or result.stdout}")

            self.signals.finished.emit({"success": True, "log": log})
        except Exception as e:
            self.signals.finished.emit({"success": False, "message": str(e), "log": log or "Worker de delecao falhou."})