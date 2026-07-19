# 炉心残冬

《炉心残冬》项目仓库。

当前仓库已完成代码 Patch 000：在文档归档骨架之上建立最小 Python 工程、配置校验入口和自动化测试入口。本阶段尚未实现游戏机制。

## 目录概览

- `docs/`：项目文档
- `data/`：数据文件
- `src/`：源文件
- `tests/`：测试文件

上传内容前请阅读 [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md) 与 [docs/INDEX.md](docs/INDEX.md)。

## 技术方案

- Python 3.12；正式运行代码只使用标准库。
- pytest 是可选开发依赖，不是生产依赖。
- 游戏逻辑、数据配置和未来 UI 分离。
- 数值与玩家文案后续分别从 `data/` 配置和 `text_id` 注册系统读取。

## 开发命令

无需安装第三方依赖即可运行统一测试：

```text
python -m unittest discover -s tests -t . -v
```

安装可选测试依赖和项目入口：

```text
python -m pip install -e ".[test]"
python -m pytest
python -m furnace_winter validate-config data
```

Patch 000 的技术决策、边界和冲突处理记录见 `docs/handoff/PATCH-000：仓库初始化与施工规则验证.md`。
