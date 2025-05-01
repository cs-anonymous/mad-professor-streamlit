export PORT=8502
export PYTHON=`which python`
kill -9 $(lsof -t -i :$PORT)
nohup $PYTHON app.py 2>&1 > app.log 2>&1 &