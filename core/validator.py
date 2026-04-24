"""
test_validator.py - 简洁测试代码校验（含项目结构上下文）
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.llm_client import LLMClient


def test_code_validator():
    """测试代码校验"""

    config = {
        "provider": "ollama",
        "model_name": "qwen3-coder",
        "base_url": "http://localhost:11434",
        "temperature": 0.1,
        "max_tokens": 1024
    }
    client = LLMClient(config)

    # 模拟项目结构
    project_structure = """
src/
├── config/
│   └── db.js
├── models/
│   └── user.js
└── utils/
    └── helper.js
"""

    # 测试代码（有导入错误）
    code = '''
import mongoose from 'mongoose';
import { logger } from '../utils/logger.util';

const connectDB = async () => {
  try {
    await mongoose.connect(process.env.MONGO_URI, {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    });
    logger.info('MongoDB Connected');
  } catch (error) {
    logger.error('Error:', error);
  }
};

export default connectDB;
'''

    prompt = f"""检查代码的导入错误。

项目结构：
{project_structure}

代码：
{code}

输出 JSON：
{{"valid": true}} 或 {{"valid": false, "errors": ["错误1", "错误2"]}}
只输出 JSON。"""

    print("正在检查代码...")
    response = client.chat([
        {"role": "system", "content": "你是代码审查专家，只输出 JSON。"},
        {"role": "user", "content": prompt}
    ])

    print(f"原始响应:\n{response}\n")

    match = re.search(r'\{.*\}', response, re.DOTALL)
    if match:
        data = json.loads(match.group())
        if data.get("valid"):
            print("✅ 代码没有发现问题")
        else:
            print(f"❌ 发现问题: {data.get('errors', [])}")
    else:
        print("无法解析响应")


if __name__ == "__main__":
    test_code_validator()