# 验证记录

日期：2026-10-27。插件：Smart FBX Materials 1.0.0。

## 实际引擎测试

| 验证项目 | UE 5.5.4（40574608） | UE 5.6.0（43139311） |
| --- | --- | --- |
| Python 启动与 ImportSubsystem 绑定 | 通过 | 通过 |
| Tools 菜单注册 | 通过 | 通过 |
| 铜机械小兵 FBX 导入为 SkeletalMesh | 通过 | 通过 |
| Skeleton 保存并重新打开项目加载 | 通过 | 通过 |
| Base Color / Normal / Metallic / Roughness 四图匹配 | 通过 | 通过 |
| 四个材质属性输入节点连接 | 通过 | 通过 |
| sRGB、Normalmap / Masks 压缩、绿色通道翻转 | 通过 | 通过 |
| 重复修复不增加资产，保留材质引用 | 通过 | 通过 |
| 静态 Cube FBX 导入与材质绑定 | 通过 | 通过 |
| 常规 FbxFactory 导入触发自动修复 | 通过 | 通过 |

UE 5.6 测试使用用户指定工程，插件通过项目默认发现机制启动。
UE 5.5 使用工作区独立无 C++ 模块测试项目，不降级或转换用户的 UE 5.6 项目。
测试脚本：工作区 `ue_test_import.py`。
两份实际引擎报告位于各工程 `Saved/SmartFbxMaterials/verification.json`。

验证样例：用户提供的“铜机械小兵”FBX 与四张 PBR 贴图；原始资源不随仓库分发。
该 FBX 为 binary FBX 7400，含 Skin、一个材质槽和失效的 Tripo Linux 服务端贴图路径。
插件独立扫描其同名子文件夹，识别四张本机图片；不修改源 FBX 和图片。

最终模型：`/Game/SmartFBX_Verification/BronzeSoldierValidated/SK_Asset_f04cb78f`。
模型目录下 `SmartMaterials` 保存生成的材质与纹理。
`StaticCube` 与 `AutomaticCube` 是用于验证静态网格/导入回调的额外测试资产。
最初的 `BronzeSoldier` 文件夹是诊断迭代产物，正式验收使用 `BronzeSoldierValidated`。

## 独立匹配测试

9 项 unittest 通过：嵌套中文目录、Tripo 命名、冲突不随机选图、多材质防误配、
显式覆盖、丢失文件、打包图通道命名、Unicode 名称摘要、ASCII FBX/非法 FBX 检查。

## 本轮修复

- 显式保存 Skeleton，修复初次导入可见、重启后骨架丢失的问题。
- 通过源路径与用途找回 Interchange 改名的贴图，修复重复修复失败的问题。
- 贴图使用 TextureFactory，减少异步导入和目标名称改写的不确定性。
- 源贴图修改时间变化时重新导入插件自己的资产。
- 材质启用 SkeletalMesh 使用标记，检查节点连接 API 返回值。
- 遇到同名用户材质/纹理不覆盖；搜索限制深度与文件数量。

## 验证范围

实际测试使用 `-nullrhi`，验证真实导入、资产保存/加载和材质图，不构成最终灯光、
GPU Shader 编译、法线凹凸方向及画面观感验收。原始 Tripo 法线按 OpenGL 假设处理，
必要时通过设置关闭绿色通道翻转。
Tk 文件选择对话框尚未人工点击验证；Tools 菜单注册和 Python 指定路径导入已验证。
后续 UE 版本需重跑回归；不能据此宣称所有未来 UE 版本均已通过测试。
任意复杂 FBX 材质、UDIM、分层材质及动画导入不在 1.0 范围内。
