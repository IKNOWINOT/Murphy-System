# Simple script to create a file
with open('created_by_murphy.txt', 'w') as f:
    f.write("This file was created by Murphy System at " + str(__import__('datetime').datetime.now()))
print("File created successfully!")
