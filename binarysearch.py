# Generic binary search.

# le indicates whether to go left or right?
def binary_search(l, r, le):
    while r > l:
        m = (l + r)//2
        # print(l, r, m)
        if le(m):
            # Go right.
            l = m + 1
        else:
            r = m - 1
    if le(l):
        return l
    elif le(r):
        return r
    #assert r == l
    return m

def search_list(list_, le):
    return binary_search(0, len(list_) - 1, lambda x: le(list_, x))

def basic_search_list(list_, value):
    return search_list(list_, lambda li, x: li[x] <= value)
        

if __name__ == "__main__":
    pass
