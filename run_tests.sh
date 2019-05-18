rm -r ./test.run &>/dev/null
cp -r ./test ./test.run
cd test.run

coverage run ./test.py
coverage combine
coverage report
coverage html -i -d ../html

python3 ./test.py

cd ..

