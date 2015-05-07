Installing oseoserver
=====================

Installation
------------

* Create a new django project or start with an existing one
* Install pyxb with the OGC schema bindings

  .. code:: bash

     # download, build and install pyxb with the OGC schemas
     pip install --download $PIP_DOWNLOAD_CACHE pyxb
     BUILD_DIR=$HOME/build
     mkdir -p $BUILD_DIR
     PYXB_ARCHIVE=$(ls $PIP_DOWNLOAD_CACHE | grep -i "^pyxb")
     tar --directory=$BUILD_DIR -xvf $PIP_DOWNLOAD_CACHE/$PYXB_ARCHIVE
     cd $BUILD_DIR/$(ls $BUILD_DIR)
     export PYXB_ROOT=$(pwd)
     pyxb/bundles/opengis/scripts/genbind
     python setup.py install
     cd -
     rm -rf $BUILD_DIR

* Download the `django-oseoserver` package and install it
* Add `oseoserver` to installed_apps
* Add the following oseoserver dependencies to installed_apps (they have
  been automatically installed when you installed django-oseoserver:

  * grappelli
  * actstream
  * tastypie
  * mailqueue

* Add the following settings to your `settings.py` file:

  .. code:: python

     # celery options
     CELERY_RESULT_BACKEND = "redis://"
     CELERY_TASK_RESULT_EXPIRES = 18000 #: 5 hours
     CELERY_ACCEPT_CONTENT = ["application/json", "pickle"]
     CELERY_TASK_SERIALIZER = "json"
     CELERY_RESULT_SERIALIZER = "json"
     CELERY_REDIRECT_STDOUTS = True
     CELERYD_HIJACK_ROOT_LOGGER = False
     CELERY_IGNORE_RESULT = False
     CELERY_DISABLE_RATE_LIMITS = True
     CELERY_IMPORTS = ("oseoserver.tasks",)
     CELERYBEAT_SCHEDULE = {
         "delete_expired_oseo_files" : {
             "task": "oseoserver.tasks.delete_expired_oseo_files",
             "schedule": crontab(hour=10, minute=30),
         },
         "terminate_expired_subscriptions": {
             "task": "oseoserver.tasks.terminate_expired_subscriptions",
             "schedule": crontab(hour=00, minute=30)
         },
     }

     # settings for django-mail-queue
     MAILQUEUE_CELERY = True

  Some of these settings can be fine tuned, but these default values should be
  good to get you started. You should read the documentation on celery and
  django-mail-queue to find out more.


* In order to have oseoserver send you e-mail notifications you must also
  include the usual e-mail related settings for django:

  * `EMAIL_HOST`
  * `MAIL_PORT`
  * `MAIL_HOST_USER`
  * `MAIL_HOST_PASSWORD`
  * `MAIL_USE_TLS`
  * `MAIL_USE_SSL`

* Add urlconf for `oseoserver`
* Run `migrate` to update the structure of the database
* Run the `oseodefaults` management command in order to insert default
  data into the database
* If you are configuring a blank django run the `createsuperuser` management
  command in order to generate an administrator. Be sure to assign it an
  e-mail address
* Use the admin interface to create a tastypie API key for the admin user.
* Installation is done! Now move on to the
  :doc:`configuration <configuration>` section so that you can get oseoserver
  ready to be used

Example
-------

Put here an example showing how to create a blank django project and install
oseoserver into it
