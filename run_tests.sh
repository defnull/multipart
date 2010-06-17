rm -r ./test.run &>/dev/null
cp -r ./test ./test.run
cp ./src/* ./test.run/
wget -O "./test.run/bottle.py" "http://github.com/defnull/bottle/raw/master/bottle.py"
cd test.run

coverage run ./test.py
coverage combine
coverage report
coverage html -i -d ../html

echo
echo "2to3 ..."
2to3 -w *.py &> /dev/null

python3 ./test.py

cd ..

