def list2path(ids):
    id2ip = lambda id : f'{id}.{id}.{id}.{id}'
    ids = list(map(id2ip, ids))
    data = ':0:0.00,0.00,0.00,0.00:|'.join(ids+[''])
    return data[:-1]

ids = input().split()
print(list2path(ids))