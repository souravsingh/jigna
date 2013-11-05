#
# Enthought product code
#
# (C) Copyright 2013 Enthought, Inc., Austin, TX
# All right reserved.
#
# This file is confidential and NOT open source.  Do not distribute.
#


# Standard library.
import inspect
import json
import os
import sys
from os.path import abspath, dirname, join

# 3rd party library.
from jinja2 import Template

# Enthought library.
from traits.api import (
    Any, Dict, HasTraits, Instance, Property, Str, TraitInstance, TraitListEvent
)

# Jigna libary.
from jigna.core.html_widget import HTMLWidget
from jigna.core.wsgi import FileLoader


#### HTML templates ###########################################################

DOCUMENT_HTML_TEMPLATE = """
<html ng-app>
  <head>
    <script type="text/javascript" src="{{jquery}}"></script>
    <script type="text/javascript" src="{{angular}}"></script>
    <script type="text/javascript" src="{{jigna}}"></script>
    <script type="text/javascript">
      $(document).ready(function(){
        jigna.initialize('{{model_name}}', '{{id}}');
      });
    </script>

    {{head_html}}

  </head>

  <body>
    {{body_html}}
  </body>
</html>
"""


class Bridge(HasTraits):
    """ Bridge that handles the client-server communication. """

    #### 'Bridge' protocol ####################################################

    #: The broker that we provide the bridge for.
    broker = Any

    def emit(self, event):
        """ Emit an event. """

        jsonized_event = json.dumps(event)

        # This looks weird but this is how we fake an event being 'received'
        # on the client side when using the Qt bridge!
        self.widget.execute_js('jigna.bridge.on_event(%r);' % jsonized_event)

        return

    def recv(self, jsonized_request):
        """ Handle a request from the client. """

        request  = json.loads(jsonized_request)
        response = self.broker.handle_request(request)

        return json.dumps(response);

    #### 'QtWebKitBridge' protocol ############################################

    #: The 'HTMLWidget' that contains the QtWebLit malarky.
    widget = Any


class Broker(HasTraits):
    """ Broker that exposes Python objects to JS. """

    #### 'Broker' protocol ####################################################

    #: The bridge that provides the communication between Python and JS.
    bridge = Instance(Bridge)
    def _bridge_changed(self, trait_name, old, new):
        if old is not None:
            old.broker = None

        if new is not None:
            new.broker = self

        return

    def emit_object_changed_event(self, obj, trait_name, old, new):
        """ Emit an event to let clients know that an object has changed. """

        print 'emit_object_changed_event', obj, trait_name, new

        if isinstance(new, TraitListEvent):
            trait_name = trait_name[:-len('_items')]
            new        = getattr(obj, trait_name)

        else:
            if isinstance(new, HasTraits) or isinstance(new, list):
                self.register_object(new)

        event = dict(
            obj        = str(id(obj)),
            trait_name = trait_name,
            # fixme: This smells a bit, but marhsalling the new value gives us
            # a type/value pair which we need on the client side to determine
            # what (if any) proxy we need to create.
            new        = self._marshal(new)
        )

        self.bridge.emit(event)

        return

    def handle_request(self, request):
        """ Handle a request from the client. """

        try:
            method    = getattr(self, request['kind'])
            args      = self._unmarshal_all(request['args'])
            result    = method(*args)
            exception = None

        except Exception, e:
            exception = repr(sys.exc_type)
            result    = repr(sys.exc_value)

        return dict(exception=exception, result=self._marshal(result))

    def register_object(self, obj):
        """ Register the given object with the broker. """

        self._id_to_object_map[str(id(obj))] = obj

        return

    #### Handlers for each kind of request ####################################

    def call_method(self, obj, method_name, *args):
        """ Call a method on a registered object. """

        method = getattr(obj, method_name)

        return method(*args)

    def get_instance_info(self, obj):
        """ Return a description of an instance. """

        obj.on_trait_change(self.emit_object_changed_event)

        info = dict(
            trait_names  = obj.editable_traits(),
            method_names = self._get_public_method_names(type(obj))
        )

        return info

    def get_list_info(self, obj):
        """ Returns a description of a list. """

        info = dict(
            length = len(obj)
        )

        return info

    def get_list_item(self, obj, index):
        """ Return the value of a list item. """

        return obj[index]

    def get_trait(self, obj, trait_name):
        """ Return the value of a trait on an object. """

        return getattr(obj, trait_name)

    def set_list_item(self, obj, index, value):
        """ Set an item in a list. """

        obj[index] = value

        return

    def set_trait(self, obj, trait_name, value):
        """ Set a trait on an object. """

        setattr(obj, trait_name, value)

        return

    #### Private protocol #####################################################

    #: All instance and lists that have been accessed via the bridge.
    #:
    #: { str id : instance_or_list obj }
    _id_to_object_map = Dict

    def _get_public_method_names(self, cls):
        """ Get the names of all public methods on a class.

        Return a list of strings.

        """

        public_methods = []
        for c in inspect.getmro(cls):
            if c is HasTraits:
                break

            for name in c.__dict__:
                if not name.startswith( '_' ):
                    value = getattr(c, name)
                    if inspect.ismethod(value):
                        public_methods.append(name)

        return public_methods

    def _marshal(self, obj):
        """ Marshal a value. """

        if isinstance(obj, HasTraits):
            obj_id = str(id(obj))
            self._id_to_object_map[obj_id] = obj

            type  = 'instance'
            value = obj_id

        elif isinstance(obj, list):
            obj_id = str(id(obj))
            self._id_to_object_map[obj_id] = obj

            type  = 'list'
            value = obj_id

        else:
            type  = 'primitive'
            value = obj

        return dict(type=type, value=value)

    def _marshal_all(self, iter):
        """ Marshal all of the values in an iterable. """

        return [self._marshal(obj) for obj in iter]

    def _unmarshal(self, obj):
        """ Unmarshal a value. """

        if obj['type'] == 'primitive':
            value = obj['value']

        else:
            value = self._id_to_object_map[obj['value']]

        return value

    def _unmarshal_all(self, iter):
        """ Unmarshal all of the values in an iterable. """

        return [self._unmarshal(obj) for obj in iter]


class JignaView(HasTraits):
    """ A factory for HTML/AngularJS based user interfaces. """

    #### 'JignaView' protocol #################################################

    #: The base url for all resources.
    base_url = Property(Str)
    def _get_base_url(self):
        return self._base_url

    def _set_base_url(self, url):
        self._base_url = join(os.getcwd(), url)
        return

    #: The HTML for the *body* of the view's document.
    body_html = Str

    #: The underlying toolkit control that renders HTML.
    control = Property(Any)
    def _get_control(self):
        return self._widget.control

    #: The HTML for the *head* of the view's document.
    head_html = Str

    def show(self, model):
        """ Create and show a view of the given model. """

        self._broker.register_object(model)
        self._load_html(self._get_html(model), self.base_url)
        self.control.show()

        return

    #### Private protocol #####################################################

    #: Shadow trait for the 'base_url'.
    #:
    #: fixme: not sure what this buys us?!?
    _base_url = Str
    def __base_url_default(self):
        return os.getcwd()

    #: The broker that manages the objects shared via the bridge.
    _broker = Instance(Broker)
    def __broker_default(self):
        return Broker(bridge=Bridge(widget=self._widget))

    #: The toolkit-specific widget that renders the HTML.
    _widget = Any
    def __widget_default(self):
        return self._create_widget()

    def _create_widget(self):
        """ Create the HTML widget that we use to render the view. """

        hosts = {
            'resources.jigna': FileLoader(
                root = join(abspath(dirname(__file__)), 'resources')
            )
        }

        widget = HTMLWidget(
            callbacks        = [('recv', self._recv)],
            python_namespace = 'qt_bridge',
            hosts            = hosts,
            open_externally  = True,
            debug            = True
        )
        widget.create()

        return widget

    def _recv(self, request):
        """ Handle a request from a client. """

        return self._broker.bridge.recv(request)

    def _get_html(self, model):
        """ Get the HTML document for the given model. """

        template = Template(DOCUMENT_HTML_TEMPLATE)
        html     = template.render(
            jquery     = 'http://resources.jigna/js/jquery.min.js',
            angular    = 'http://resources.jigna/js/angular.min.js',
            jigna      = 'http://resources.jigna/js/jigna.js',
            model_name = 'model',
            id         = id(model),
            body_html  = self.body_html,
            head_html  = self.head_html
        )

        return html

    def _load_html(self, html, base_url):
        """ Load the given HTML into the widget. """

        self._widget.load_html(html, base_url)

        return

#### EOF ######################################################################
