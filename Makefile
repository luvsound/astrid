.PHONY: test build

test:
	python -m unittest discover -s tests -p 'test_*.py' -v

clean:
	rm -rf build/
	rm -rf astrid/*.c
	rm -rf astrid/*.so

build:
	python setup.py develop
