.PHONY: test build

install:
	./scripts/init.sh

update:
	./scripts/update.sh

test:
	./venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v

clean:
	rm -rf build/
	rm -rf astrid/*.c
	rm -rf astrid/*.so

run:
	./venv/bin/astrid server

console:
	./venv/bin/astrid console

build:
	./venv/bin/python setup.py develop
