

l = [11,22,33,44,55]


for i,item in enumerate(l):

    next = i+1
    prev = i-1

    if i == len(l)-1:
        next = 0

    print(l[(prev)],l[(i)],l[(next)])