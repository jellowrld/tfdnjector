# 🧩 Jell's TFD Njector

[![Windows](https://img.shields.io/badge/OS-Windows-blue)](https://www.microsoft.com)  
[![Release](https://img.shields.io/github/v/release/jellowrld/tfdnjector?color=orange)](https://github.com/jellowrld/tfdnjector/releases/latest)  
[![Downloads](https://img.shields.io/github/downloads/jellowrld/tfdnjector/latest/total?color=green)](https://github.com/jellowrld/tfdnjector/releases/latest)  
[![Stars](https://img.shields.io/github/stars/jellowrld/tfdnjector?color=yellow)](https://github.com/jellowrld/tfdnjector/stargazers)

A Windows GUI tool for **The First Descendant** that automatically detects the game folder, cleans logs, optionally deletes CFG files, and injects a DLL — all in a **single executable**.  

---

## Features

- 🕹️ **Automatic Game Detection**  
  Finds your Steam installation and locates the game folder automatically.  

- 🧹 **Pre-launch Cleanup**  
  Clears logs, crash reports, webcache, and pipeline caches before launch.  

- 🗑️ **Optional CFG Deletion**  
  Delete `CFG.ini` prior to launch using a simple checkbox.  

- ⏱️ **BlackCipher Delay Slider**  
  Adjust `BlackCipherDelay` for instant injection (values from **2500** to **60000 ms**) directly in the GUI.  

- 💉 **DLL Injection**  
  Inject a user-selected DLL into the game process. Compatible with Athruns, Tivmo, and Blizzies DLLs.  

- 🔄 **Auto-Inject**  
  Monitors the game process and injects the DLL automatically. If the game crashes, the injector resets automatically—no need to restart the tool.  

- 🖤 **Dark-Themed GUI**  
  Clean, intuitive interface with all options easily accessible.

- 🛡️ **EAC Bypass (One and Done)**

  Retrieves old EAC files from my github repo and replaces new ones to bypass EAC.

---

## 📷 Screenshot

<p align="center">
  <img src="https://github.com/jellowrld/tfdnjector/raw/main/njector.png" alt="Injector GUI" width="600"/>
</p>

*GUI showing console, DLL browse, Delete CFG checkbox, Default Settings, Black Cipher Delay Slider and Launch button.*

---

## ⬇️ Download

Get the latest release here:  

[**⬇ Download Jell's TFD Njector.exe**][https://github.com/jellowrld/tfdnjector/releases/download/1.3/TFD.Njector.exe](https://github.com/jellowrld/tfdnjector/releases/download/1.3/TFD.Njector.exe)

---

## 📝 Usage

1. Download the **`.exe`**.  
2. Launch the injector.  
3. Browse and select your DLL file.  
4. Check **🗑️ Delete CFG** if you want the CFG file removed before launch.
5. Check **📝 Default Settings (Run this Once)** To apply default optimal graphic settings for Flectorite.
6. Click **🚀 Launch TFD** — logs will be cleaned and the DLL injected automatically.  
7. Monitor the console for status updates.  

---

## ⚠️ Notes

- Tested on **Windows 10/11**.  
- Only compatible with the **Steam version** of *The First Descendant*.  
- Ensure your DLL is compatible with the game’s 64-bit process.  
- Anti-virus software may flag DLL injection tools. Use at your own risk.  

---

## 📄 License

Provided **as-is** for educational and personal use. Use responsibly.  
