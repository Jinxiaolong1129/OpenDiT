
respacings=[
    [10, 10, 10, 10, 10, 10, 10, 10, 5, 5],
    [10, 10, 10, 10, 10, 10, 10, 5, 5, 5],
    [10, 10, 10, 10, 10, 10, 5, 5, 5, 5],
    [10, 10, 10, 10, 10, 5, 5, 5, 5, 5],

    [10, 10, 10, 10, 10, 10, 10, 10, 2, 2],
    [10, 10, 10, 10, 10, 10, 10, 2, 2, 2],
    [10, 10, 10, 10, 10, 10, 2, 2, 2, 2],

    [2, 2, 2, 2, 2, 10, 10, 10, 10, 10],
    [2, 2, 2, 2, 10, 10, 10, 10, 10, 10],
    [2, 2, 2, 10, 10, 10, 10, 10, 10, 10],
    [2, 2, 10, 10, 10, 10, 10, 10, 10, 10],

    [5, 5, 5, 5, 5, 10, 10, 10, 10, 10],
    [5, 5, 5, 5, 10, 10, 10, 10, 10, 10],
    [5, 5, 5, 10, 10, 10, 10, 10, 10, 10],
]



def calculate_list_sum(respacings):
    list_sums = []
    for respacing in respacings:
        numbers = [int(num) for num in respacing]
        list_sum = sum(numbers)
        list_sums.append(list_sum)

    return list_sums

list_sums = calculate_list_sum(respacings)
list_sums = set(sorted(list_sums))
print(list_sums)
