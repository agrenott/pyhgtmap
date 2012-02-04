all: fileformat_pb2.py osmformat_pb2.py

fileformat_pb2.py: fileformat.proto
	protoc --python_out=../phyghtmap osmformat.proto

osmformat_pb2.py: osmformat.proto
	protoc --python_out=../phyghtmap fileformat.proto
