# Smart FBX Materials · UE 5.5+

面向 Unreal Editor 的 FBX/PBR 材质导入插件，使用引擎自带 Python，不需要编译 C++。

## 安装与使用

将整个 `SmartFbxMaterials` 目录复制到项目 `Plugins`，重启编辑器。
插件依赖 Python Editor Script Plugin 与 Editor Scripting Utilities，描述文件会声明依赖。
在 Edit → Plugins 中确认启用 **Smart FBX Materials**。

工具菜单：`Tools → Smart FBX Materials`。

- **Import FBX + PBR Materials…**：选择 FBX，导入模型并匹配附近贴图。
- **Repair Selected Mesh Materials**：在 Content Browser 选中已导入网格，再修复其材质。
- 普通导入的 FBX 网格通过 ImportSubsystem 回调自动尝试匹配。对于异步 Interchange
  未触发完成回调的版本，请使用插件专用导入或“修复选中网格”。

命令行或 Output Log 的 Python 输入同样支持：

```python
import smart_fbx_materials as s
s.import_fbx(r'C:/Models/Bronze/Bronze.fbx', '/Game/Art/Bronze')
```

## 匹配与材质

最多扫描 FBX 同目录下 3 层、4096 个文件，不扫描相邻整个资源库，不跟随目录符号链接。
支持 PNG、JPG/JPEG、TGA、TIF/TIFF、BMP、EXR。

| 贴图角色 | 常见名称 | UE 设置/连接 |
| --- | --- | --- |
| Base Color | basecolor、base_color、albedo、diffuse、tripo_rgb | sRGB，Base Color |
| Normal | normal、_N、法线 | Linear，Normalmap 压缩，Normal |
| Roughness | roughness、_R、粗糙 | Linear，Masks 压缩，R → Roughness |
| Metallic | metallic、metalness、_M、金属 | Linear，Masks 压缩，R → Metallic |
| AO | occlusion、_AO | Linear，R → Ambient Occlusion |
| Emissive | emissive、emission | sRGB，Emissive Color |
| ORM/ARM | _ORM、_ARM | R=AO，G=Roughness，B=Metallic |
| RMA | _RMA | R=Roughness，G=Metallic，B=AO |

独立 Roughness/Metallic/AO 贴图优先于打包图。多个候选同分时不随机选图，报告警告。
多材质网格要求贴图名包含相应材质槽名称，或者配置显式覆盖；不会给每个槽都贴同一套图。
已生成贴图通过源路径、用途和修改时间查找；源文件更新后重新修复会更新贴图。
当前实现面向标准 UV0 PBR 贴图，不恢复任意 FBX 程序材质、UDIM、置换或分层混合网络。
骨骼模型保留骨架；专用导入默认不额外导入动画和物理资产。
导入时显式保存新建骨架，确保关闭并重新打开编辑器后仍保留 Skeleton 引用。

## 设置

可选配置位于项目 `Saved/SmartFbxMaterials/settings.json`，未提供时使用下列默认值：

```json
{
  "automatic_repair": true,
  "flip_normal_green": true,
  "destination": "/Game/SmartFBX",
  "two_sided": false,
  "masked": false,
  "overrides": {},
  "material_overrides": {
    "FBXMaterialSlotName": {
      "base_color": "Textures/MyColor.png",
      "normal": "Textures/MyNormal.png"
    }
  }
}
```

Tripo/Blender 常用 OpenGL 法线，默认翻转绿色通道以适配 UE；若源贴图已经是 DirectX
法线，请将 `flip_normal_green` 设为 false。仅凭文件名不能证明实际法线约定。
透明度不从文件名自动推断；明确需要镂空时开启 `masked` 并提供 opacity 贴图。
不会读取 Unity 的 Smoothness 当作 Roughness；应先转换 `Roughness = 1 − Smoothness`。

## 资产保护与诊断

源 FBX/图片只读。生成的 UE 材质和纹理位于模型目录的 `SmartMaterials` 下，使用
ASCII 名称与稳定摘要避免中文清洗后重名。只重建带本插件 Owner 元数据的材质，遇到
同名用户资产即中止。专用 FBX 导入不启用覆盖已有网格；再次导入可能生成新网格，
需要保持网格引用时请使用 UE Reimport，然后修复选中模型。

每个模型的匹配与警告报告输出到 `Saved/SmartFbxMaterials/*_report.json`。
保存失败、路径错误或无网格输出会明确报错，不把无材质结果当作成功。

## 兼容性边界

最低目标 UE 5.5；UE 5.5/5.6 使用公开 Python 编辑器 API，后续版本需重新跑回归。
仅 Editor 使用，不在运行时执行 Python。Windows 文件选择使用引擎附带 Tk；平台缺少
Tk 时仍可通过 Python API 指定文件或使用普通导入后修复。不会强制关闭项目的
Interchange 全局设置。

参考 Epic 官方 [AssetImportTask](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetImportTask?application_version=5.5)、
[FbxImportUI](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FbxImportUI?application_version=5.5)、
[ImportSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ImportSubsystem?application_version=5.6)。
