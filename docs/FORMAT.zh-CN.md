# Band 9 v2 `.face` 格式说明（compile.exe 4.22）

日期：2026-10-14。范围：Mi Create 所带 m0tral 编译器的 `DefaultPacker`、Band 9 (`DeviceType=366`) 路径。**不是所有小米机型/全部 v2 文件的通用规范**。以下用自己的话描述格式，不含反编译源码。所有未注明端序的整数均 little-endian；地址均为文件绝对偏移，非 RVA。

## 1. 证据与可信度

- **R（REA 静态观察）**：`validation/rea-managed-inline.json`，Evidence ID `ev_af643b37e124e3b33c6e5818c1d918cb967e9f88fd8aeb0cd0662c7615adf997`。目标 SHA-256 `bf0f7230f4fd08ed45d9a9fd1b8359a679b04b87998825a259e0ef49ba239f30`，12,999,680 B，PE32 x86 CIL，程序集 Compiler 4.22.0.0，.NET Framework 4.7.2。嵌入 XiaomiWatch.Common 4.15.0.0；无须运行程序集。REA 此操作只提供元数据，**不把后续反编译内容冒称为 REA 输出**。
- **D（ILSpy 静态反编译）**：ILSpy 对 compile.exe 4.22 的反编译输出 `MiWatchCompiler.Packers/DefaultPacker.cs`（下称 `DP`）；其嵌入的 `XiaomiWatch.Common.dll` 的反编译输出（下称 `C`）。反编译代码未随本仓库分发。原 DLL SHA-256 `f464864963da58a8144343c6d9f351e9c2e334412a21d5f81d98cb37c96a29f1`。这些是恢复的 C#，不是原作者开放的源码。
- **S（公开参考）**：RedKage/Xiaomi_Band_Tools commit `f413b3453093d68a34155c54cf14092bd84f23f9`，可用于在线定位同名类；README 说明为反编译项目，不是成熟的跨平台编译器。本次以实际目标 D 复核，不仅凭参考源码推断。
- **B（样本实测）**：Vadim170/miband9-minimal-analog commit `1249c462986061a7bc1021c5fde513fa276ca193`，`AnalogFull.fprj` + `AOD/AOD.fprj` + `images/` + `AnalogFull.face`。原文件/复编均 1,094,548 B，SHA-256 `d531249c5c2f2335ce00b464cf75007d82dd0dc750bd26116bbe5fc3187003b3`，**逐字节相同**。此处“原编译器产物”依据上游项目文档及文件；本次没有运行原编译器，也没有小米官方签名背书。资源/偏移详见 `validation/AnalogFull-components.json`。
- **G（GB 安装入口源码）**：本地 Gadgetbridge commit `d4bd8367314982032a593fadab8d80db64b71d01`，`XiaomiFWHelper.java:388–442`，及 `XiaomiInstallHandler.java:125–167`。仅证明离线解析/尺寸闸门，不证明手环接受和运行。
- 具体版本、159 个输入文件大小/摘要见 `validation/provenance.json`。Mi Create commit `d7aa9e682d43a2454363dbaaba809125901f7b06`。

**反编译源码与 compile.exe 的一致性（2026-10-14 复核）**：`DP` 与 `C` 是 ilspycmd 11.1 直接对 `compile.exe` 及其嵌入的 `XiaomiWatch.Common.dll` 反编译的结果，因此就是 compile.exe 4.22 的代码。再与 Xiaomi_Band_Tools（S）逐文件比对：`DefaultPacker`、`MagikHelper`、`EnumerationHelper`、`MiBand9RleCompressor`、`RleEncoder`、`ImageCompressFactory`、`FaceItemDataSrc`、`FaceWidget`/`DigitalNum`/`ImageList`/`AnalogClock`/`Image`、`FaceProject`、`RedmiWatch4ActionPacker` 的字符串、数字字面量序列一致（`DefaultPacker` 849 个字面量逐一相同）；`Namespace.cs` 与 `DefaultPacker` 仅反编译器写法不同（switch 表达式、`string.Format` 与插值字符串、数组长度标注）。这是字面量级核对，不是语义等价证明；最终以 B 的逐字节复编为准。

证据标记：**观察**＝D/B/G 有直接对应；**推测**＝命名/语义解释，没有固件运行证据；**未知**＝当前路径不使用，未硬猜。

## 2. 总布局与打包顺序

```text
0x0000          文件头，168 B (0xA8)
0x00A8          faceCount 个 face descriptor，每个 88 B (0x58)
其后            所有 face 的资源索引表（每个索引项 16 B）
其后            face 0 的 element payload → widget payload → image → image list
                → animation → app → action → option
其后            AOD（若有）及其他 face 的相同 payload 序列
最后            主 face 预览图；尾部 0–3 个 00 对齐字节
```

**观察**：DP `Exec:88–213`、`CountElementsSize:1158–1330`。先为所有 face 预留索引，再写数据；每个 payload 开始按 4 B 对齐，索引记录的长度不包含末尾 padding。索引表中的 offset 是绝对文件地址。

**观察**：主项目优先，AOD 次之，其他同目录 `.fprj` 随后。原编译器的其他 face 顺序受 `Directory.GetFiles` 影响；本实现排序以保证可重放，指定 `.fprj` 可明确主项目。AOD 由 `AOD/images` 存在触发，需唯一 `AOD/*.fprj`。

**观察**：没有 ZIP、时间戳、随机数、文件总长度字段或末尾签名。当前编译路径直接写完整数组，不计算 CRC/MD5/SHA 等内部校验和（DP `Exec`、B 全字节覆盖）。本文的 SHA-256 是外部验证证据，不写进 `.face`。**未知**：固件/伴侣 App 是否另有外部认证策略，不能由无内部 CRC 推导为必能安装。

## 3. 文件头：168 B，每一字节的范围

| 偏移 | 大小 | Band 9 值/含义 | 证据 |
|---|---:|---|---|
| 0x00 | 4 | `5A A5 34 12` magic | 观察：DP `header:17`，B@0 |
| 0x04–0x0F | 12 | 全 0；保留，语义未知 | 观察：DP header，B |
| 0x10 | 4 | `0x00000800`；编译器名为版本字段，准确固件语义未知 | 观察：DP `SetupHeader:1332`，B@0x10 |
| 0x14–0x1B | 8 | 全 0；其他机型可能另写 flags，Band 9 不写 | 观察：DP SetupHeader，B |
| 0x1C | 1 | face 数量（包含 AOD），1–255 | 观察：DP SetupHeader，B=2 |
| 0x1D | 1 | 0 | 观察：DP header，B |
| 0x1E | 1 | bit 2 (`0x04`) 有 AOD；bit 1 (`0x02`) 非 AOD face 多于一个；其余位本路径 0 | 观察：DP SetupHeader，B=4 |
| 0x1F | 1 | 0 | 观察：DP header，B |
| 0x20 | 4 | 主预览资源绝对偏移 | 观察：DP `SetupPreview:532`，G，B=`0x102334` |
| 0x24–0x27 | 4 | 0，未使用 | 观察：DP header，B |
| 0x28–0x67 | 64 | 默认 ASCII ID `167210065` + NUL + 零填充 | 观察：DP header，B；G 从0x28读至NUL并要求纯数字 |
| 0x68–0xA7 | 64 | 主 Screen.Title 的 UTF-8 + NUL + 零填充 | 观察：DP SetupHeader，B=`Analog Full` |

本实现为 ID 强制 9 位 ASCII 数字、名称强制 1–63 UTF-8 字节，以免越界。原程序不严格限制标题长度；这是本实现的安全约束，不是声称固件只能接受这些值。

**重要观察**：DeviceType 366 本身不直接写入该头；它在编译时选择头参数和图片 codec。原 CLI 只对第 5 个参数做 `int.Parse`（`Program.MainBody`），并未用其改头 ID，`.fprj` 根 `Id` 也未被 FaceProject 类序列化处理。Mi Create 在编译完成后用 `src/utils/binary.py::WatchfaceBinary.setId` 改写 0x28 的 9 B（`src/main.py:1939-1940`）。本实现 `--id` 是这个确定性的后处理等价项。不能拿 CLI 示例里的 `1461256429` 当输出 ID。

### 名称本地化变体（不是本编译器的输出）

G：若 0x68 起为 `FF FF FF FF`，则 `u32@0x74` 为名称语言块地址，`u32@0x78` 为大小。语言块是 `u64` 可用语言 bitmask → 每个 set bit 对应一个 `u32` 字符串字节长度 → 按 bit 顺序串接的 UTF-8 内容。按语言/地区、同语言、首个可用语言依次选择。`validate_gb.py` 支持这条读路径；打包器仅输出普通 UTF-8 名称。**未知**：其他生产器在该 header 的额外语义。

## 4. Face descriptor：88 B

基址 `F = 0xA8 + index*0x58`。

| 相对偏移 | 内容 | 证据 |
|---|---|---|
| +0x00 (4 B) | 0，原 faceHeader 的初始值；不是 face 序号 | 观察：DP faceHeader，B 两个 descriptor 都为0 |
| +0x04 (4 B) | 主 face 预览偏移；其他 face `FFFFFFFF` | 观察：DP Exec/SetupPreview；B@0xAC及0x104 |
| +0x08…+0x57 | 10 对 `{u32 count, u32 indexTableOffset}`，顺序见下表 | 观察：DP CountElementsSize |

| kind | count/offset 相对偏移 | 类别 | 本实现 |
|---:|---|---|---|
| 0 | +0x08 / +0x0C | 显示元素（draw order） | 支持 |
| 1 | +0x10 / +0x14 | 保留，count=0；offset 指向下一类起点 | 保留0 |
| 2 | +0x18 / +0x1C | 单图资源 | 支持 |
| 3 | +0x20 / +0x24 | 图集资源 | 支持 |
| 4 | +0x28 / +0x2C | 动画 | 已读格式，未实现 |
| 5 | +0x30 / +0x34 | App 内嵌文件 | 已读封装，未实现 |
| 6 | +0x38 / +0x3C | 保留，count=0；offset 与 widget 表起点相同 | 保留0 |
| 7 | +0x40 / +0x44 | 动态组件 widget | 支持 number/list/hand |
| 8 | +0x48 / +0x4C | option，原路径 count 恒0 | 保留0 |
| 9 | +0x50 / +0x54 | 按钮 action | 已读封装，未实现 |

**观察**：空类别仍写当时的索引游标，offset 不一定为0，不能把它误认为缺失资源。B 主 face：element 表 `0x158/8`、image 表 `0x1D8/5`、list 表 `0x228/3`、widget 表 `0x258/6`；AOD：`0x2B8/7`、`0x328/5`、`0x378/2`、`0x398/5`。

## 5. 通用资源索引：16 B

| +偏移 | 类型 | 内容 | 证据 |
|---|---|---|---|
| +0 | u32 | 资源 ID：byte0=index，byte1/2=0，byte3=kind | 观察：DP SetupElements/Widgets/Image/ImageList |
| +4 | u32 | 0（保留） | 观察：各 Setup 方法及 B |
| +8 | u32 | payload 的绝对偏移 | 同上 |
| +12 | u32 | payload 原始字节数，不含对齐零 | 同上 |

例如 image ID=0x02000001，widget ID=0x07000003；磁盘字节分别为 `01 00 00 02`、`03 00 00 07`。

**观察**：Band 9 的 image/list/widget ID 跨 face 递增，不在 AOD 重置（`EnumerationHelper.Reset*`）；element 序号每 face 从0起；每种 image list 在单个 face 内按文件名序列去重，跨 face 不去重。原代码用字符串哈希做去重，本实现用路径元组避免哈希碰撞误并。**边界**：需不超过每类256个 ID；超过显式报错，不模仿原 byte 溢出。

## 6. Element payload：16 B（绘图实例）

| 相对偏移 | 类型 | 内容 | 证据 |
|---|---|---|---|
| +0 | u32 | 引用 image、widget、animation、app 或 action 的 ID | 观察：DP SetElementProp |
| +4 | i16 | X anchor | 同上 |
| +6 | i16 | Y anchor | 同上 |
| +8 / +12 | u32/u32 | 0 / 0 | 同上与 B |

静态图片直接引用 kind2；数值、图集、指针引用 kind7。element 表顺序即绘制次序。Shape27 展开为 hour/minute/second 三个 element（仅存在的手针）。它的 Background_ImageName 在这条编译路径没有单独打包，须另建静态背景组件。`Alpha`/`Visible_Src` 也未在这些记录里实现：本实现只接受255/0，防止用户以为支持了透明度/条件显示。

数字 X anchor：Left 原 X；Center 加 `firstGlyphWidth*Digits/2` 的整数部分；Right 加 `firstGlyphWidth*Digits`。不加 Spacing。指针坐标=`Widget.X/Y + Widget.Width/Height//2 - 各手针 pivot`。证据：DP SetElementProp；B day 原 X=102，字宽34，Digits=2，最终X=136（0x88），element@0x408。

## 7. Widget payload

共用：+0 两字节为**数据源字符串解析值的 big-endian**，与其余字段的 LE 不同；+8 为 u32 资源引用。DP SetWidgetProp、C `FaceItemDataSrc.Parse` / `BinaryExtender.SetWord`。

例：`Value_Src="2031"` → `20 31` 两字节，若固件按 LE 解释是0x3120；`5031` → `50 31`，固件0x3150。长写法 `40009031` = hex低四位0x9031 + 前缀0x4000 =0xD031，写`D0 31`。不是十进制2031，更不是把字符串转为 LE u32。

### 7.1 Digital number（Shape32）：20 B

| +偏移 | 内容 | 证据 |
|---|---|---|
| 0–1 | Value_Src | 观察：DP SetWidgetProp |
| 2 | Digits，u8 | 同上 |
| 3 | `0x10 | blankingFlag | alignmentBits`；Blanking=0时bit2=1，否则0；Left=1、Center=2、Right=0 | 同上与 ParseAlignment |
| 4–7 | Band 9全0（其他机型会写+6） | 观察：DP |
| 8–11 | kind3图集ID | 观察：DP |
| 12 | 0 | 观察：DP与B |
| 13 | Spacing，u8 | 观察：DP |
| 14–15 | 名称含 `_angle[N]` 时写u16，范围0<N<3600，否则0 | 观察：DP、C FaceWidget.GetAngle；固件角度单位为0.1°是推测 |
| 16–19 | 可选 `_ref[name]` 静态图片ID；默认0 | 观察：DP；本实现拒绝_ref |

图集索引0…9为十个数字，10为负号、11为小数点（Mi Create properties 定义；实际负温/小数固件表现未实测）。B day widget@0x494：source=`18 12`，digits=2，flags=0x12，listID=0x03000001，剩余为0。

### 7.2 Indexed image list（Shape31）：16+4*N B

| +偏移 | 内容 | 证据 |
|---|---|---|
| 0–1 | Index_Src | 观察：DP |
| 2 | 0；DefaultIndex 未写入本路径 | 观察：DP |
| 3 | 0x20 | 观察：DP |
| 4–7 | 0 | 观察：DP |
| 8–11 | kind3图集ID | 观察：DP |
| 12–15 | 有自定义索引时u32=512 (`00 02 00 00`) | 观察：DP |
| 16起 | N个i32选择值，与图集顺序对应 | 观察：DP、C FaceWidgetImageList.HasCustomValues |

`BitmapList="(0):a.png|(1):b.png"`。该4.22库即使索引连续也强制 custom map，N=2时payload24B。+14角度写入会被+12这个u32覆盖（原行为），不要把它描述成已验证的list旋转功能。B weekday@0x468，44B，索引0…6；battery@0x4A8，420B，索引0…100。

### 7.3 Analog hand（Shape27展开）：32 B/针

| +偏移 | 内容 | 证据 |
|---|---|---|
| 0–1 | hour=`0811`、minute=`1011`、second=`1811` | 观察：DP |
| 2 / 3 | 0 / 0x30 | 观察：DP |
| 4–5 | 0 | 观察：DP |
| 6–7 | u16刷新参数，默认1000；second `_smooth[N]`可改为30…1000 | 观察：DP、C FaceWidget.GetSmoothValue；毫秒单位为推测 |
| 8–11 | kind2手针图ID | 观察：DP |
| 12–16 | 0 | 观察：DP |
| 17 | hour=24，minute/second=60 | 观察：DP |
| 18–19 | 0 | 观察：DP |
| 20–21 / 22–23 | u16旋转中心X/Y | 观察：DP |
| 24–25 | 0 | 观察：DP |
| 26–27 | hour=7200，minute/second=3600 | 观察：DP；与十进制度映射的运行语义待实测 |
| 28–31 | 0 | 观察：DP |

B三针widget@0x64C/0x66C/0x68C，中心(96,245)。`HourHandCorrection_En`/`MinuteHandCorrection_En` 在DP中未被读取，不应因XML设置为1就宣称编译器实现了平滑。**兼容细节**：AOD第二针和第一针用AOD/images，但第三针取主images；本实现为字节兼容保留该行为。

### 7.4 其余动态记录（未实现/未样本验证，不纳入支持承诺）

以下为D观察的封装，固件语义仍未知：

- 圆弧/直线进度（Shape29/42）：40 B。+0 source，+3为0x40（圆弧）或0x50（`lineprogress_`），+8图片ID；+16为端帽标记（启用圆帽=0，否则1）；+20/+24为u32 RangeMin/RangeMax左移8位；+28/+30为u16 pivot；+32/+34为i16 起角/扫角（Band9圆弧按角度*10、终角减始角；直线写原start/end）；+36圆弧半径u16，+38线宽u16；其余0。DP SetWidgetProp与 C FaceWidgetCircleProgressPlus.WidgetSize。Shape29旧类的某些初始化路径不完整，不能无样本断言等价于所有Shape42。
- 一般container（Shape34）没有完整的嵌套绘图设置；`app_`容器走App引用。本实现均拒绝，不静默丢弃。
- 未识别Shape、文本、拼接记录：DefaultPacker并无完整实现，**未知/不支持**。不能根据Common里有同名类便声称能编译。

## 8. 图片和图集编码（Band 9特有）

### 8.1 单图资源：12 B头 + 一个frame

| +偏移 | 内容 | 证据 |
|---|---|---|
| 0–3 | `06 04 00 00` | 观察：C MiBand9RleCompressor.GetHeader |
| 4–5 / 6–7 | u16 width / height | 观察：DP PackImageData |
| 8–11 | u32 frame字节数（含frame的8B压缩头） | 同上 |
| 12起 | frame | 同上 |

type6对应RGB565+alpha，compression4为此RLE路径（C与G的preview读取交叉印证）。宽高取PNG本身，不按Widget.Width/Height重采样。Band9 compressor忽略withAlfa参数，始终保留alpha；`_rgba`/`_rgb`不会切换成本实现之外的编码。预览使用完全相同的单图结构；支持192×490或122×310。

### 8.2 图集资源：12 B头 + N个u32长度 + N个frame

头前四字节为`06 NN 04 00`，NN=N；+4/+6为每帧宽高；+8的u32是**所有frame长度之和，不包含4*N长度表**。每帧单独压缩，不插入帧间padding；整个资源结尾再做4B对齐。所有帧必须同宽高。数字组件与索引组件共享此载体。观察：DP SetupImageList、C GetHeader、B的101帧电量列表。

### 8.3 每帧：8 B压缩头 + RLE v10包

- +0…3：`E0 21 A5 5A`。
- +4…7：u32 `(decodedByteLength << 4) | 3`；decodedByteLength=`width*height*3`；低4位为每像素3B。
- 解压像素顺序：逐行、从左到右，每像素`u16 RGB565 little-endian`后紧接`u8 alpha`（straight alpha，不预乘）。颜色量化为 `floor(R*31/255)<<11 | floor(G*63/255)<<5 | floor(B*31/255)`；**不是**简单右移。输入Magick导出BGRA，因此反编译函数的第一channel虽然名字像R，实际为B。
- RLE包：1B控制字，低7位为count；高位0时随后3B像素重复count次；高位1时随后count*3B为字面像素。原encoder仅把单个非重复像素写成`81 pixel`，重复run为2…127；更长run切分。可跨行run。
- 观察证据：C MiBand9RleCompressor.Compress/PackRgbaToRgb565Alpha、RleEncoder.EncodeV10_3；DP MagikHelper.GetBitmapFromPng/List；B全部146帧成功解码且重新编码全字节相同。`face_codec.py`另有随机/长run/错误包测试。

**不支持**：`_nocompress`为原厂特殊名字功能，库中的该分支与Band9的3B转换不一致，缺实物样本；本实现明确拒绝，不生成“看似通过GB”但可能不可用的文件。其他v2机型的RGB888、RGB565分离alpha、其他RLE版本不能套用此节。

## 9. 其他资源（静态观察的封装；尚未实现）

| 类别 | payload及来源 | 可信边界 |
|---|---|---|
| kind4 动画 | 12B：+0 u32图集ID，+4..5=0，+6 u16 delay，+8 u16 count，+10..11=0；由名称`anim_[count@delay]`解析。DP SetupAnimation；C AnimationHelper | 观察封装，未固件实测 |
| kind5 App文件 | 20B头后接ASCII相对路径及原始文件：+0 u32 `(pathLength<<24)|fileLength`，+4..19为0；descriptor长度=20+pathLength+fileLength。DP SetupApp | 观察封装；不是Android APK，不在本次执行 |
| kind8 option | DP CountElementsSize枚举恒0，实际不输出；不可从死代码证明固件格式 | 未知/不支持 |
| kind9 action | Band9选C ActionFactory→RedmiWatch4ActionPacker，56B。+0..1为动作名对应标记，+40..43为4B动作码，+48 u32图片ID，+52/+54 u16宽高；其余0。DP SetupAction、C Pack/GetActionSize。element引用kind9 | 观察封装；动作常量表不在本实现内重分发、未样本/运行验证 |

## 10. 已确认与尚未确认

**已确认**：本文的Band9文件头、descriptor/索引结构、四种基础组件、AOD、RGB565+A及RLE，可从原项目重建出相同字节。`inspect_face.py`能把样本反解为组件、源、坐标和图片清单，检查指针/长度/资源引用并解压所有帧。

**推测/待真机**：天气数字是否等于GB推送值，负温和三位温度行为、AQI范围、刷新频率、固件安装策略。数字2031/5031的**写入编码已确认**，其**运行值未在本次观察**。

**不承诺完整兼容**：按钮、App、动画、progress、容器、字体/文本、多语言写入、各种特殊名称和全部v2设备。本实现对已识别但未实现的功能报错。时间/天气数字路径和公开样本路径覆盖完整；不把一对样本的成功扩大为所有`.fprj`项目均可靠。

## 参考入口

- https://github.com/ooflet/Mi-Create/tree/d7aa9e682d43a2454363dbaaba809125901f7b06
- https://github.com/RedKage/Xiaomi_Band_Tools/tree/f413b3453093d68a34155c54cf14092bd84f23f9
- https://github.com/Vadim170/miband9-minimal-analog/tree/1249c462986061a7bc1021c5fde513fa276ca193
- https://github.com/m0tral/EasyFace
