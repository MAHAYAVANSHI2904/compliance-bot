import sys

filepath = 'Invoice_Hub.py'
with open(filepath, 'rb') as f:
    data = f.read()

# Replace corrupted magnifying glass ðŸ” 
data = data.replace(b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\x8d', b'\xf0\x9f\x94\x8d') # 🔍
data = data.replace(b'\xc3\xb0\xc5\xb8\xe2\x84\xa2\xc2\x9a', b'\xf0\x9f\x9a\x80') # 🚀
data = data.replace(b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\xb1', b'\xf0\x9f\x9b\x91') # 🛑

with open(filepath, 'wb') as f:
    f.write(data)
