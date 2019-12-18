import time


from kafka import KafkaProducer
from kafka.errors import KafkaError

from volttron.platform import jsonapi

'''
example
kafka_topic: "msg-to-volttron"
device_point: "fake-campus/fake-building/fake-device/PowerState"
new_value: 1
'''

# produce json messages
producer = KafkaProducer(bootstrap_servers=['127.0.0.1:9092'],
                         value_serializer=lambda m: jsonapi.dumps(m).encode('utf-8')
                         )
new_new_value = 0
while True:
    try:
        menu = int(input('1: Command by user input, 2: Command by json file - '))

        if menu == 1:
            pass
            # kafka_topic, device_point, new_new_value = raw_input('input kafka_topic, device_point, new_new_value: ').split(' ')
            # 
            # msg = {
            #     'message': 'message from VOLTTRON to Cloud',
            #     'new_value': new_value,
            #     'device_point': device_point
            # }
            # print('msg: {}\n'.format(msg))
            # # send message to broker
            # producer.send(kafka_topic, msg)

        elif menu == 2:
            with open('message.json') as f:
                data = jsonapi.load(f)
                kafka_topic = data["kafka_topic"]
                message_list = data["message_list"]

                for message in message_list:
                    sender  = message['sender']
                    topic = message['topic']
                    value = message['value']
                    description = message['description']
                    msg = {
                        'kafka_message_sender': sender,
                        'topic': topic,
                        'value': value,
                        'description': description
                    }
                    print('msg: {}'.format(msg))
                    # send message to broker
                    producer.send(kafka_topic, msg)
                print('')


    except Exception as e:
        print(e)
        break
