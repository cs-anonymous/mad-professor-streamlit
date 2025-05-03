#!/bin/bash

# VPN
export http_proxy="http://127.0.0.1:7897" && export https_proxy="http://127.0.0.1:7897"

# 1. 杀死占用 8501 端口的旧进程
# kill -9 $(sudo lsof -t -i :8501)
pkill -f "streamlit run stream.py"
sleep 1  # 等待进程完全退出

# 2. 后台启动 Streamlit，并记录日志到 stream.log
export STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true
nohup streamlit run stream.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.fileWatcherType none \
    --logger.level=info \
    > stream.log 2>&1 &

# 3. 检查是否启动成功
sleep 3
if pgrep -f "streamlit run stream.py" >/dev/null; then
    echo "✅ Streamlit 已启动（PID: $(pgrep -f "streamlit run stream.py")）"
    echo "📄 日志文件: stream.log"
    echo "🌍 访问地址: http://$(hostname -I | awk '{print $1}'):8501"
else
    echo "❌ Streamlit 启动失败，请检查日志: stream.log"
fi

tail -f stream.log