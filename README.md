<img width="128" height="128" alt="fe713dda-d347-43c6-8224-2eaf92c0cf03" src="https://github.com/user-attachments/assets/e9e0c9bf-4cb3-4e70-8736-29d5958f4a2d" />

关于项目：  
  
Python Flash Tools——Python刷机工具箱  
使用Python开发的刷机工具  
会自动下载依赖文件  
有刷机、备份、命令、解锁、小米线刷、9008和bootrom功能  
支持多彩主题  
使用mtkclient和安卓SDK等开源项目拼凑而成，遵守GPL-3开源协议  
不足之处请提交lssues  
注：1.1stable之前版本无法正常运行（其实是功能不可用）  
仅适用于Windows操作系统（因为依赖文件）  
Power By 哔哩哔哩：澜澈LanChe  

如何使用？ 
  
V1.4之前（包括V1.5-Lite）可以直接运行打包好的.exe文件  
V1.5只后（不含V1.5-Lite）只能运行run.bat启动主程序  
运行run.bat的同时会弹出python3.11.2的安装程序（微软自动安装）  
安装时请勾选下方的添加到系统PATH  
如果没有弹出安装程序请手动运行.zip文件下的python.exe手动安装

安装必备依赖：
  
V1.6之前：  
  py -m pip install PyQt5  
  或  
  "<你的Python路径>" -m pip install PyQt5  
V1.7 Beta版：  
  无需安装依赖  
V1.7 Beta-wxPython版：  
  py -m pip install wxPython  
  或  
  "<你的Python路径>" -m pip install wxPython  
V1.7 Beta-PySimpleGUI版：
  py -m pip install PySimpleGUI  
  或  
  "<你的Python路径>" -m pip install PySimpleGUI  
  
开始运行：  
  
安装Python结束run.bat可能会退出（我不知道），重新运行即可  
然后就能进入主程序了  
会自动检测python路径  
注：V1.5和V1.6 Beta都没有第一次运行报存依赖文件的功能，自己设置的会保存  
V1.6 Stable已经修复该问题

