Celery tasks
============

Tasks that run on-demand
------------------------

Oseoserver does most of the work involved in processing its orders
asynchronously. This allows the service to remain responsive and stable,
avoiding usage peaks. The task processing queue is provided by integrating
the excelent `celery`_ project.

.. _celery: http://www.celeryproject.org

* `process_product_order`
* `process_product_order_batch`
* `process_subscription_order_batch`
* `process_online_data_access_item`
* `update_product_order_status`
* `delete_oseo_file`


Periodic tasks
--------------

In order to keep your ordering server in good shape, some tasks must be
executed periodically. Oseoserver uses a celery beat daemon

* `delete_expired_oseo_files`
* `terminate_expired_subscriptions`

Setting up Celery
-----------------

Adding custom tasks to the schedule
###################################


