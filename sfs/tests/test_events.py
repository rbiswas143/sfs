import unittest

import sfs.events as events


class EventSubscriptionTests(unittest.TestCase):

    def test_multiple_subscriptions(self):
        total = 0

        @events.subscriber('test')
        def subscriber1(val1, val2=10):
            nonlocal total
            total += val1 + val2

        @events.subscriber('test')
        def subscriber2(val1, val2=20):
            nonlocal total
            total += val1 * val2

        # Invokes all subscribers
        events.invoke_subscribers('test', 3, val2=5)
        self.assertEqual(total, (3 + 5) + (3 * 5))

    def test_distinct_subscriptions(self):
        total = 0

        @events.subscriber('test1')
        def subscriber1(val1, val2=10):
            nonlocal total
            total += val1 + val2

        @events.subscriber('test2')
        def subscriber2(val1, val2=20):
            nonlocal total
            total += val1 * val2

        # Invokes all subscribers for a key
        events.invoke_subscribers('test2', 3, val2=5)
        self.assertEqual(total, 3 * 5)

    def test_unique_subscription(self):
        @events.subscriber('test_a', unique=True)
        def subscriber_a1():
            pass

        # Cannot add subscriber to a key marked unique
        with self.assertRaises(events.SubscriberExists):
            @events.subscriber('test_a')
            def subscriber_a2():
                pass

        @events.subscriber('test_b')
        def subscriber_b1():
            pass

        # Cannot add unique subscriber to an existing event key
        with self.assertRaises(events.SubscriberExists):
            @events.subscriber('test_b', unique=True)
            def subscriber_b2():
                pass

    def test_command_key(self):
        command = 'test_command'

        # Returns valid cli_exec key given a cli_exec name
        self.assertEqual(
            events.events['COMMAND_EXECUTION'] + '_' + command,
            events.command_key(command)
        )
