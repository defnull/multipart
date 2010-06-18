rm -r ./test.run &>/dev/null
cp -r ./test ./test.run
cp ./src/* ./test.run/
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

