Custom order processing class
=============================

Oseoserver handles OSEO requests and responses. However, it does not take care
of the actual processing of orders.

For processing the order you must integrate you own custom processing class.
This allows you to use whatever way is most suitable to identify the ordered
items, fetch them from their storage location and apply any defined custom
options. This processing class must implement the following interface:

.. py:method:: get_subscription_batch_identifiers(timeslot, collection, options, **params)

   :arg timeslot: The timeslot for the subscription batch that will be created
   :type timeslot: datetime.datetime
   :arg collection: The collection that is being ordered
   :type collection: basestring
   :arg options: Any custom ordering options that may have been requested at
       the time the subscription was created.
   :type options: dict
   :return: A list of order item identifiers that is used to create order items
       for the current subscription batch
   :rtype: list(string)

   Create order item identifiers for each subscription batch.

   This method is called by
   :py:meth:`oseoserver.server.OseoServer.dispatch_subscription_order` when
   a new batch is about to be created and sent to processing.
   Use this method to decide how to create the order items relevant for
   subscription batches.

.. py:method:: get_subscription_duration(order_specification)

   :arg order_specification: The custom options that were requested with the
       order
   :type order_specification: dict
   :return: A pair of datetime objects specifying the starting and ending
       times for the requested subscription order
   :rtype: (:py:class:`datetime.datetime`, :py:class:`datetime.datetime`)

   Return a temporal interval for subscription orders.

   This method is called by :py:meth:`oseoserver.operations.submit.Submit.create_order`
   when the order is being created in oseoserver's database.

   Use this method to be able to set the starting and ending time for
   a subscription. These parameters can either be given by the requesting
   client (if you decide that there should be such parameters) or determined
   by some other way. This method is expected to return 

.. py:method:: parse_extension()

.. py:method:: parse_option()

.. py:method:: process_item_online_access()

.. py:method:: package_files()

.. py:method:: clean_files()
