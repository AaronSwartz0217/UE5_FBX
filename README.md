# UE5 FBX · Smart FBX Materials

UE 5.5+ 编辑器插件：导入 FBX 时自动扫描相关 PBR 贴图，创建材质并绑定网格。
使用引擎自带 Python，安装无需编译 C++。

已实测 **UE 5.5.4** 和 **UE 5.6.0**。后续版本需重新运行回归测试。

## 功能

- 识别 Tripo、常见英文 PBR 和部分中文贴图名称，支持 FBX 下三级目录扫描。
- 支持 Base Color、Normal、Roughness、Metallic、AO、Emissive 及 ORM/ARM、RMA 打包图。
- 自动设置 sRGB、法线/数据贴图压缩和法线绿色通道翻转。
- 保留 StaticMesh / SkeletalMesh 类型，显式保存新生成的 Skeleton。
- 普通 FBX 导入后自动尝试修复，也可手动修复 Content Browser 中选中的网格。
- 多候选不随机选图；多材质槽可通过名称与显式覆盖分配不同贴图。
- 重复修复复用插件生成的材质与纹理，不覆盖同名用户资产。

## 安装

1. 下载或克隆本仓库。
2. 把 **SmartFbxMaterials** 文件夹复制到 `<UE项目>/Plugins/SmartFbxMaterials`。
3. 重启 Unreal Editor，在 Edit → Plugins 确认插件已启用。
4. 工具菜单中打开 **Tools → Smart FBX Materials**。

插件声明依赖 `PythonScriptPlugin` 与 `EditorScriptingUtilities`。

## 使用

- **Import FBX + PBR Materials…**：选择源 FBX，导入模型、创建并绑定材质。
- **Repair Selected Mesh Materials**：修复已导入的选中网格。

也可以在编辑器 Output Log 的 Python 模式执行：

```python
import smart_fbx_materials as bridge
bridge.import_fbx('D:/Assets/Bronze/Bronze.fbx', '/Game/Art/Bronze')
```

默认设置与法线格式、多材质覆盖等说明见 [插件使用说明](SmartFbxMaterials/README.md)。
导入报告保存在项目的 `Saved/SmartFbxMaterials/`。

## 测试

不依赖 Unreal 的匹配逻辑测试：

```shell
python -m unittest discover -s tests -v
```

引擎集成测试需自行准备一份具有单材质槽、四张 PBR 贴图的骨骼 FBX；测试不随仓库提供模型或贴图。
Windows PowerShell 示例：

```powershell
$env:SMART_FBX_TEST_SOURCE = 'D:/Assets/Bronze/Bronze.fbx'
& 'C:/Program Files/Epic Games/UE_5.6/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' `
    'D:/Projects/Test/Test.uproject' `
    '-ExecutePythonScript=D:/Source/UE5_FBX/ue_test_import.py' `
    -unattended -nosplash -nullrhi -nosound -NoSourceControl
```

请使用已安装插件的测试工程。测试会向 `/Game/SmartFBX_Verification/` 写入网格、材质和纹理，
并在 `Saved/SmartFbxMaterials/` 生成静态网格测试文件及验证报告；不会修改关卡。
再次运行可检查资产重新加载及重复修复行为。

已完成的引擎测试与范围见 [验证记录](SmartFbxMaterials/VALIDATION.md)。
`-nullrhi` 检查资产与材质图，不替代最终 GPU 编译和灯光下的视觉验收。

## 打包

```shell
python package_smart_fbx.py
```

生成 `SmartFbxMaterials-1.0.0-UE5.5plus.zip`，仅打包插件源码与说明，排除缓存。

## 范围

用于编辑器资产管线；不提供运行时 FBX 导入。复杂程序材质、UDIM、动画导入和最终光照匹配
不在 1.0 范围内。法线默认假设源文件为 OpenGL 格式；DirectX 法线应关闭绿色通道翻转。

许可证：[MIT](LICENSE)。
