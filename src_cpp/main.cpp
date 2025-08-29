#include <windows.h>
#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <tlhelp32.h>
#include <shlobj.h>
#include <fstream>
#include "sdk/public/steam/steam_api.h"
#include <iomanip>
#include <sstream>
#include <algorithm>

const int STEAM_APP_ID = 250820;

FILETIME GetLocalTimestamp(const std::string& path);
void UploadSave(ISteamRemoteStorage* remoteStorage, const std::string& saveFilePath, const char* remoteSaveFileName, const std::string& configDir);
void DownloadSave(ISteamRemoteStorage* remoteStorage, const std::string& saveFilePath, const char* remoteSaveFileName, const std::string& configDir);
void WriteStatusFile(const std::string& remoteSaveFileName, const std::string& configDir);
void PerformSync(bool isFinalSync, const std::string& localSavePath, const std::string& remoteSaveFileName, const std::string& configDir);
void ListRemoteFiles(const std::string& gameFolder);
void LogHistory(const std::string& message, const std::string& configDir);
std::wstring s2ws(const std::string& s);


int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);

    std::string localSavePath;
    std::string remoteSaveFileName;
    std::string configDir;
    std::string gameFolderForList; 

    bool syncNow = false;
    bool uploadOnly = false;
    bool listRemote = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--localpath" && i + 1 < argc) localSavePath = argv[++i];
        else if (arg == "--remotename" && i + 1 < argc) remoteSaveFileName = argv[++i];
        else if (arg == "--configdir" && i + 1 < argc) configDir = argv[++i];
        else if (arg == "--sync-now") syncNow = true;
        else if (arg == "--upload-only") uploadOnly = true;
        else if (arg == "--list-remote" && i + 1 < argc) {
            listRemote = true;
            gameFolderForList = argv[++i];
        }
    }

    if (syncNow) {
        if (localSavePath.empty() || remoteSaveFileName.empty() || configDir.empty()) {
            std::cerr << "[ERRO] Uso: --sync-now --localpath <path> --remotename <name> --configdir <path>" << std::endl;
            return 1;
        }
        PerformSync(false, localSavePath, remoteSaveFileName, configDir);
        return 0;
    }

    if (uploadOnly) {
        if (localSavePath.empty() || remoteSaveFileName.empty() || configDir.empty()) {
            std::cerr << "[ERRO] Uso: --upload-only --localpath <path> --remotename <name> --configdir <path>" << std::endl;
            return 1;
        }
        PerformSync(true, localSavePath, remoteSaveFileName, configDir);
        return 0;
    }

    if (listRemote) {
        ListRemoteFiles(gameFolderForList);
        return 0;
    }
    
    std::cout << "AltCloud On-Demand Sync Tool" << std::endl;
    std::cout << "Nenhum modo de operacao valido especificado." << std::endl;
    std::cout << "Modos disponiveis: --sync-now, --upload-only, --list-remote" << std::endl;
    
    return 1;
}

void WriteStatusFile(const std::string& remoteSaveFileName, const std::string& configDir) {
    if (configDir.empty()) {
        std::cerr << "[ERRO] Diretorio de config nao fornecido para WriteStatusFile." << std::endl;
        return;
    }
    std::string safeRemoteName = remoteSaveFileName;
    std::replace(safeRemoteName.begin(), safeRemoteName.end(), '/', '_');
    std::string statusFileName = configDir + "\\status_" + safeRemoteName + ".json";
    
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    long long timestamp = static_cast<long long>(now_time);

    std::ofstream statusFile(statusFileName);
    if (statusFile.is_open()) {
        statusFile << "{\n";
        statusFile << "  \"last_upload_timestamp\": " << timestamp << "\n";
        statusFile << "}\n";
        statusFile.close();
        std::cout << "[STATUS] Arquivo de status '" << statusFileName << "' atualizado." << std::endl;
    } else {
        std::cerr << "[ERRO] Nao foi possivel abrir o arquivo de status para escrita: " << statusFileName << std::endl;
    }
}

void LogHistory(const std::string& message, const std::string& configDir) {
    if (configDir.empty()) return;
    std::string logFilePath = configDir + "\\altcloud_history.log";
    std::ofstream logFile(logFilePath, std::ios::app);
    if (logFile.is_open()) {
        auto now = std::chrono::system_clock::now();
        std::time_t now_time = std::chrono::system_clock::to_time_t(now);
        char time_str[26];
        ctime_s(time_str, sizeof(time_str), &now_time);
        time_str[strlen(time_str) - 1] = '\0';
        logFile << "[" << time_str << "] " << message << std::endl;
    }
}

void PerformSync(bool isForceUpload, const std::string& localSavePath, const std::string& remoteSaveFileName, const std::string& configDir) {
    std::string logMessage;
    if (isForceUpload) {
        std::cout << "\n[SYNC] Iniciando upload forcado para " << remoteSaveFileName << "..." << std::endl;
        logMessage = "Upload forcado iniciado para " + remoteSaveFileName;
    } else {
        std::cout << "\n[SYNC] Iniciando sincronizacao inteligente para " << remoteSaveFileName << "..." << std::endl;
        logMessage = "Sincronizacao inteligente iniciada para " + remoteSaveFileName;
    }
    LogHistory(logMessage, configDir);
    
    std::ofstream appid_file("steam_appid.txt");
    appid_file << STEAM_APP_ID;
    appid_file.close();

    if (!SteamAPI_Init()) {
        std::cerr << "[ERRO] Falha ao conectar a API da Steam." << std::endl;
        remove("steam_appid.txt");
        return;
    }

    ISteamRemoteStorage* remoteStorage = SteamRemoteStorage();
    
    if (remoteStorage && !localSavePath.empty()) {
        FILETIME localFileTime = GetLocalTimestamp(localSavePath);
        int64 remoteFileTime = remoteStorage->GetFileTimestamp(remoteSaveFileName.c_str());
        bool localFileExists = (localFileTime.dwHighDateTime != 0 || localFileTime.dwLowDateTime != 0);
        bool remoteFileExists = remoteStorage->FileExists(remoteSaveFileName.c_str());
        
        if (isForceUpload) {
            std::cout << "[DEBUG] Modo Upload Forcado." << std::endl;
            UploadSave(remoteStorage, localSavePath, remoteSaveFileName.c_str(), configDir);
        } else {
            if (remoteFileExists && (!localFileExists || *(int64*)&localFileTime < remoteFileTime)) {
                std::cout << "[DEBUG] Decisao: Baixar da nuvem." << std::endl;
                DownloadSave(remoteStorage, localSavePath, remoteSaveFileName.c_str(), configDir);
            } else if (localFileExists && (!remoteFileExists || *(int64*)&localFileTime > remoteFileTime)) {
                std::cout << "[DEBUG] Decisao: Enviar para a nuvem." << std::endl;
                UploadSave(remoteStorage, localSavePath, remoteSaveFileName.c_str(), configDir);
            } else {
                std::cout << "[DEBUG] Decisao: Arquivos ja estao em sincronia." << std::endl;
                std::cout << "[ACAO] Saves ja estao em sincronia. Nenhuma acao necessaria." << std::endl;
            }
        }
    } else {
        std::cerr << "[ERRO] Interface do Steam nao encontrada ou caminho do save local esta vazio!" << std::endl;
    }

    SteamAPI_Shutdown();
    remove("steam_appid.txt");
}

void UploadSave(ISteamRemoteStorage* remoteStorage, const std::string& saveFilePath, const char* remoteSaveFileName, const std::string& configDir) {
    std::cout << "[ACAO] Enviando save local para a nuvem como '" << remoteSaveFileName << "'..." << std::endl;
    std::ifstream saveFile(saveFilePath, std::ios::binary | std::ios::ate);
    if (saveFile.is_open()) {
        std::streamsize size = saveFile.tellg();
        saveFile.seekg(0, std::ios::beg);
        std::vector<char> buffer(size);
        if (saveFile.read(buffer.data(), size)) {
            if (remoteStorage->FileWrite(remoteSaveFileName, buffer.data(), size)) {
                std::cout << "[SUCESSO] Upload do save concluido (" << size << " bytes)." << std::endl;
                LogHistory("Upload concluido para " + std::string(remoteSaveFileName), configDir);
                WriteStatusFile(remoteSaveFileName, configDir);
            } else {
                std::cerr << "[ERRO] Falha ao escrever o arquivo na Steam Cloud!" << std::endl;
                LogHistory("ERRO: Falha no upload para " + std::string(remoteSaveFileName), configDir);
            }
        }
    } else {
        std::cerr << "[ERRO] Nao foi possivel abrir o arquivo de save local para leitura: " << saveFilePath << std::endl;
        LogHistory("ERRO: Nao foi possivel abrir o arquivo de save local: " + saveFilePath, configDir);
    }
}

void DownloadSave(ISteamRemoteStorage* remoteStorage, const std::string& saveFilePath, const char* remoteSaveFileName, const std::string& configDir) {
    std::cout << "[ACAO] Baixando save '" << remoteSaveFileName << "' da nuvem..." << std::endl;
    
    std::string backupPath = saveFilePath + ".local_backup";
    if (CopyFileA(saveFilePath.c_str(), backupPath.c_str(), FALSE)) {
         std::cout << "[INFO] Backup do save local criado em: " << backupPath << std::endl;
    }

    int32_t fileSize = remoteStorage->GetFileSize(remoteSaveFileName);
    std::vector<char> buffer(fileSize);
    if (remoteStorage->FileRead(remoteSaveFileName, buffer.data(), fileSize)) {
        std::ofstream saveFile(saveFilePath, std::ios::binary | std::ios::trunc);
        if (saveFile.is_open()) {
            saveFile.write(buffer.data(), fileSize);
            std::cout << "[SUCESSO] Save baixado e aplicado (" << fileSize << " bytes)." << std::endl;
            LogHistory("Download concluido de " + std::string(remoteSaveFileName), configDir);
        } else {
             std::cerr << "[ERRO] Nao foi possivel escrever o save baixado no disco!" << std::endl;
             LogHistory("ERRO: Nao foi possivel escrever o save baixado no disco: " + saveFilePath, configDir);
        }
    } else {
        std::cerr << "[ERRO] Falha ao ler o arquivo da Steam Cloud!" << std::endl;
        LogHistory("ERRO: Falha ao ler o arquivo da Steam Cloud: " + std::string(remoteSaveFileName), configDir);
    }
}

void ListRemoteFiles(const std::string& gameFolder) {
    std::ofstream appid_file("steam_appid.txt");
    appid_file << STEAM_APP_ID;
    appid_file.close();
    if (!SteamAPI_Init()) { return; }

    ISteamRemoteStorage* remoteStorage = SteamRemoteStorage();
    if (remoteStorage) {
        int32 fileCount = remoteStorage->GetFileCount();
        std::cout << "[";
        bool first = true;
        for (int i = 0; i < fileCount; i++) {
            int32 fileSize;
            const char* fileName = remoteStorage->GetFileNameAndSize(i, &fileSize);
            std::string fileNameStr(fileName);

            if (fileNameStr.rfind(gameFolder + "/", 0) == 0) {
                if (!first) {
                    std::cout << ",";
                }
                std::cout << "{";
                std::cout << "\"filename\":\"" << fileName << "\",";
                std::cout << "\"size\":" << fileSize << ",";
                std::cout << "\"timestamp\":" << remoteStorage->GetFileTimestamp(fileName);
                std::cout << "}";
                first = false;
            }
        }
        std::cout << "]" << std::endl;
    }
    SteamAPI_Shutdown();
    remove("steam_appid.txt");
}

FILETIME GetLocalTimestamp(const std::string& path) {
    FILETIME ft = {0};
    HANDLE hFile = CreateFileA(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (hFile != INVALID_HANDLE_VALUE) {
        GetFileTime(hFile, NULL, NULL, &ft);
        CloseHandle(hFile);
    }
    return ft;
}

std::wstring s2ws(const std::string& s) {
    int len;
    int slength = (int)s.length() + 1;
    len = MultiByteToWideChar(CP_ACP, 0, s.c_str(), slength, 0, 0);
    wchar_t* buf = new wchar_t[len];
    MultiByteToWideChar(CP_ACP, 0, s.c_str(), slength, buf, len);
    std::wstring r(buf);
    delete[] buf;
    return r;
}