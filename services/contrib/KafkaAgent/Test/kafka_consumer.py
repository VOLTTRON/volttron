from kafka import KafkaConsumer

# value_deserializer=lambda m: json.loads(m).decode('utf-8')
consumer = KafkaConsumer(bootstrap_servers=['localhost:9092'],
                        #  group_id='my-group-2',
                         )
consumer.subscribe(['msg-from-volttron'])
cnt = 0

while True:
    partition = consumer.poll(timeout_ms=1000, max_records=None)
    # obj : type dict
    if len(partition) > 0:
        print('poll - receive')
        for p in partition:
            for response in partition[p]:
                print('poll topic: {}'.format(response.topic))
                # print('poll value: {}'.format(response.value))
                # string to dict
                # dic_value = ast.literal_eval(response.value)
                print('poll value: {}'.format(response.value))
                # print('poll value: {}, new_value: {}'.format(dic_value, dic_value['new_value']))
                # print('poll value type: {}'.format(type(dic_value)))
    else:
        print('poll - no receive yet {}'.format(cnt))
        cnt += 1
