#include <windows.h>
#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <fstream>
#include <shlobj.h>
#include <algorithm>
#include <cctype>
#include "sdk/public/steam/steam_api.h"

const int STEAM_APP_ID = 250820;

std::string trim_quotes(const std::string& s) {
    std::string res = s;
    res.erase(res.begin(), std::find_if(res.begin(), res.end(), [](unsigned char ch) { return !std::isspace(ch); }));
    res.erase(std::find_if(res.rbegin(), res.rend(), [](unsigned char ch) { return !std::isspace(ch); }).base(), res.end());
    if (!res.empty() && res.front() == '"') res.erase(0, 1);
    if (!res.empty() && res.back() == '"') res.pop_back();
    return res;
}

std::string GetSteamInstallPath() {
    HKEY hKey;
    char path[MAX_PATH];
    DWORD pathSize = sizeof(path);
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Wow6432Node\\Valve\\Steam", 0, KEY_READ, &hKey) != ERROR_SUCCESS) {
        if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Valve\\Steam", 0, KEY_READ, &hKey) != ERROR_SUCCESS) {
            std::cerr << "[DEBUG] Chave do registro da Steam nao encontrada." << std::endl;
            return "";
        }
    }
    if (RegQueryValueExA(hKey, "InstallPath", NULL, NULL, (LPBYTE)path, &pathSize) != ERROR_SUCCESS) {
        RegCloseKey(hKey);
        std::cerr << "[DEBUG] Valor 'InstallPath' nao encontrado." << std::endl;
        return "";
    }
    RegCloseKey(hKey);
    return std::string(path);
}

uint32 GetMostRecentUserIDFromFile(const std::string& steamPath) {
    std::string vdfPath = steamPath + "\\config\\loginusers.vdf";
    std::ifstream vdfFile(vdfPath);
    if (!vdfFile.is_open()) return 0;
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(vdfFile, line)) lines.push_back(line);
    for (size_t i = 0; i < lines.size(); ++i) {
        if (lines[i].find("\"MostRecent\"") != std::string::npos && lines[i].find("\"1\"") != std::string::npos) {
            for (int j = i - 1; j >= 0; --j) {
                if (lines[j].find("{") != std::string::npos) {
                    if (j > 0) {
                        try {
                            return CSteamID(std::stoull(trim_quotes(lines[j - 1]))).GetAccountID();
                        } catch (const std::exception&) { return 0; }
                    }
                    break;
                }
            }
        }
    }
    return 0;
}

int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);
    std::cout << "[INFO] Deleter v4 (Logica Final) iniciado." << std::endl;

    if (argc < 2) {
        std::cerr << "[ERRO] Uso: deleter.exe \"PastaDoJogo/NomeDoSave.ext\"" << std::endl;
        return 1;
    }

    std::ofstream appid_file("steam_appid.txt");
    appid_file << STEAM_APP_ID;
    appid_file.close();

    std::cout << "[DEBUG] Inicializando SteamAPI..." << std::endl;
    if (!SteamAPI_Init()) {
        std::cerr << "[ERRO] Falha ao conectar a API da Steam." << std::endl;
        remove("steam_appid.txt"); 
        return 1;
    }
    
    ISteamRemoteStorage* remoteStorage = SteamRemoteStorage();
    if (!remoteStorage) {
        std::cerr << "[ERRO] Nao foi possivel obter a interface do Steam Remote Storage." << std::endl;
        SteamAPI_Shutdown();
        remove("steam_appid.txt");
        return 1;
    }
    
    std::cout << "[DEBUG] Aguardando API (aquecimento)..." << std::endl;
    for (int i = 0; i < 5; ++i) {
        SteamAPI_RunCallbacks();
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    std::string steamPath = GetSteamInstallPath();
    uint32 userID = GetMostRecentUserIDFromFile(steamPath);
    std::string localSaveBasePath = "";

    if (!steamPath.empty() && userID != 0) {
        localSaveBasePath = steamPath + "\\userdata\\" + std::to_string(userID) + "\\" + std::to_string(STEAM_APP_ID) + "\\remote\\";
        std::cout << "[INFO] Pasta de saves local da Steam Cloud encontrada: " << localSaveBasePath << std::endl;
    } else {
        std::cerr << "[AVISO] Nao foi possivel determinar o caminho da pasta userdata. A delecao local sera ignorada." << std::endl;
    }

    for (int i = 1; i < argc; ++i) {
        std::string remoteFileNameStr(argv[i]);
        std::cout << "-----------------------------------------------------" << std::endl;
        std::cout << "[INFO] Processando: '" << remoteFileNameStr << "'" << std::endl;

        if (!localSaveBasePath.empty()) {
            std::string localFilePath = localSaveBasePath + remoteFileNameStr;
            std::replace(localFilePath.begin(), localFilePath.end(), '/', '\\');
            
            std::cout << " -> Deletando arquivo local em: " << localFilePath << "..." << std::flush;
            if (remove(localFilePath.c_str()) == 0) {
                std::cout << " [SUCESSO]" << std::endl;
            } else {
                std::cout << " [NAO ENCONTRADO ou FALHA]" << std::endl;
            }
        }

        std::cout << " -> Enviando comando de delecao para a nuvem..." << std::flush;
        if (remoteStorage->FileDelete(remoteFileNameStr.c_str())) {
            std::cout << " [SUCESSO]" << std::endl;
        } else {
            std::cout << " [FALHA ou ARQUIVO INEXISTENTE]" << std::endl;
        }
    }

    SteamAPI_Shutdown();
    remove("steam_appid.txt");
    std::cout << "-----------------------------------------------------" << std::endl;
    std::cout << "[INFO] Processo concluido. O cliente Steam agora deve sincronizar a delecao." << std::endl;
    
    return 0;
}