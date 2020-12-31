.PHONY: test build

install:
	pip install -r requirements.txt
	git submodule update --init
	python setup.py develop

test:
	python -m unittest discover -s tests -p 'test_*.py' -v

clean:
	rm -rf build/
	rm -rf astrid/*.c
	rm -rf astrid/*.so

build:
	python setup.py develop
