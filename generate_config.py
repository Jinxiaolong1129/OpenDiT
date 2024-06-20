def generate_strings():
    result = []
    for i in range(10):
        lst = [5] * 10
        lst[i] = 3
        result.append(str(lst))
    return result

strings = generate_strings()
for s in strings:
    print(f'"{s}"')
