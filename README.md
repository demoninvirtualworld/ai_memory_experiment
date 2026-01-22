# AI 记忆能力实验平台

研究大模型不同记忆能力对人机交互的影响。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

打开 `config.py`，在第 22 行填入你的通义千问 API Key：

```python
'qwen_api_key': os.environ.get('QWEN_API_KEY', '你的API密钥'),
```

API Key 获取地址：https://bailian.console.aliyun.com/

### 3. 启动服务

```bash
python app.py
```

启动后访问：http://localhost:8000

### 4. 默认账号

- 管理员：`admin` / `psy2025`
- 普通用户：注册时选择记忆组别

---

## 实验设计

### 四种记忆水平（自变量）

| 记忆组别 | 说明 | AI 表现 |
|---------|------|--------|
| no_memory | 无记忆 | 每次对话都像第一次见面 |
| short_memory | 短期记忆 | 只记得上次对话的后1/3内容 |
| medium_memory | 中期记忆 | 记得历史对话的摘要 |
| long_memory | 长期记忆 | 完整记得所有历史对话 |

### 实验流程（4次对话）

1. **第1次**：关系建立与信息播种
2. **第2次**：记忆触发测试
3. **第3次**：深度任务支持
4. **第4次**：综合评估与告别

---

## 项目结构

```
ai_memory_experiment/
├── app.py              # Flask 主程序
├── config.py           # 配置文件（API Key 在这里）
├── models.py           # 数据模型和记忆策略
├── utils.py            # 工具类（QwenManager 等）
├── requirements.txt    # Python 依赖
├── static/             # 前端文件
│   └── index.html
└── data/               # 用户数据存储
    └── users/          # 每个用户一个 JSON 文件
```

---

## 切换模型

在 `config.py` 中修改 `model_provider`：

```python
# 使用通义千问
'model_provider': 'qwen'

# 使用 DeepSeek
'model_provider': 'deepseek'
```

---

## 常见问题

**Q: API 调用失败？**
- 检查 API Key 是否正确
- 检查网络连接

**Q: 如何查看用户数据？**
- 数据存储在 `data/users/{用户名}.json`

**Q: 如何重置所有数据？**
- 删除 `data/users/` 文件夹下的所有 JSON 文件
- 或调用 `/api/debug/reset` 接口
