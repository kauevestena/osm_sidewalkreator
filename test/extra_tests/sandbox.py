# td = {'a':1,'b':2}

# print(sorted(list(td.values())))

from math import isclose


widths = [12,18,6,2,22,28]


def get_major_dif_signed(inputval,inputlist,tol=0.5,print_diffs=False):
    diffs = []

    for value in inputlist:
        # always avoid to compare floats equally
        if not isclose(inputval,value,abs_tol=tol):
            print(value)
            diffs.append(value-inputval)

    if print_diffs:
        print(diffs)

    if diffs:
        if len(diffs) > 1:
            return inputval+max(diffs)
        else:
            return inputval+diffs[0]
    else:
        return inputval


# def within_proximity(inputval,ref,delta=0.1):


test_val = 18

print(widths)
print(test_val,get_major_dif_signed(test_val,widths,print_diffs=True))




# diffs = []

# for i,currwidth in enumerate(widths):
#     curr_diffs = []
#     for j,width in enumerate(widths):
#         if not i == j:
#             curr_diffs.append(width-currwidth)

#     diffs.append(curr_diffs)

# for i,diffslist in enumerate(diffs):
#     print(widths[i],diffslist,max(diffslist)+widths[i])