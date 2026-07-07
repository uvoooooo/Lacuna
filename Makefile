.PHONY: help install lock sync lint format test run demo web clean

help:
	@echo "make install   - 安装项目 + dev 依赖 (uv)"
	@echo "make lock      - 生成/更新 uv.lock"
	@echo "make sync      - 按 lock 同步环境"
	@echo "make lint      - ruff 检查"
	@echo "make format    - ruff 自动格式化"
	@echo "make test      - 运行 pytest"
	@echo "make run       - 运行内置示例 (CLI --demo)"
	@echo "make demo      - 启动 Gradio 演示"
	@echo "make web       - 启动本地网页版 (输入框 -> 审计卡片)"
	@echo "make clean     - 清理缓存"

install:
	uv sync --extra dev

lock:
	uv lock

sync:
	uv sync --frozen --extra dev

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

run:
	uv run python -m narrative_audit --demo

demo:
	uv run --extra demo python examples/gradio_demo.py

web:
	uv run --extra web python -m narrative_audit.webapp

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__ build dist *.egg-info
