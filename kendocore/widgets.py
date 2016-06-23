from django import forms
from django.forms.widgets import FILE_INPUT_CONTRADICTION
from django.conf  import settings
from django.template import loader
from django.utils.html import conditional_escape
from django.utils.translation import ugettext_lazy as _
from django.utils import datetime_safe, formats, six
from django.utils.dates import MONTHS
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from .compat import MULTIVALUE_DICT_TYPES, flatten_contexts

__all__ = ('TextInput','HiddenInput',)

# primero inicializamos un widget
class Widget(forms.Widget):
    is_required = False

    @property
    def is_hidden(self):
        return self.input_type == 'hidden' if hasattr(self,'input_type') else False

# el widget inicializado se pasa hacia un input para ser construido
class Input(Widget):
    template_name = 'kendo/input.html'
    input_type = None
    datalist = None

    class Media:
        css = {
        'all' : ('kendo/style/kendo.common.min.css', 'kendo/style/kendo.flat.min.css')
        }
        js = ('kendo/js/jquery.min.js', 'kendo/js/kendo.ui.core.min.js','kendo/js/kendotext.js')

    def __init__(self, *args, **kwargs):
        datalist = kwargs.pop('datalist', None)
        if datalist is not None:
            self.datalist = datalist
        template_name = kwargs.pop('template_name',None)
        if template_name is not None:
            self.template_name = template_name
        super(Input, self).__init__(*args,**kwargs)
        self.context_instance = None

    def get_context_data(self):
        return {}

    def _format_value(self, value):
        if self.is_localized:
            value  = formats.localize_input(value)


        if value is None:
            value = ''
        return force_text(value)

    def get_context(self, name, value, attrs=None):
        #inicializo el contexto a utilizar en el widget
        context = {
            'type': self.input_type,
            'name': name,
            'hidden': self.is_hidden,
            'required': self.is_required,
            'True': True,
        }

        if self.is_hidden:
            context['hidden'] = True
        if value != '':
            print 'valor de widget %s' % value
            context['value'] =self._format_value(value)

        context.update(self.get_context_data())
        context['attrs'] = self.build_attrs(attrs)

        for key, attr in context['attrs'].items():
            if attr == 1:
                # 1 == True entonces 'hey=1' se mostrara solo como una key
                if not isinstance(attr, bool):
                    context['attrs'][key] = str(attr)

        if self.datalist is not None:
            context['datalist'] = self.datalist

        return context

    def render(self, name, value, attrs=None, **kwargs):
        template_name = kwargs.pop('template_name', None)
        if template_name is None:
            template_name = self.template_name
        context = self.get_context(name, value, attrs=attrs or {'class': 'k-textbox'}, **kwargs)
        context = flatten_contexts(self.context_instance, context)
        return loader.render_to_string(template_name, context)

class TextInput(Input):
    template_name = 'kendo/text.html'
    input_type = 'text'

    def __init__(self, *args, **kwargs):
        if kwargs.get('attrs', None) is not None:
            self.input_type = kwargs['attrs'].pop('type', self.input_type)
        super(TextInput, self).__init__(*args, **kwargs)

class HiddenInput(Input):
    template_name = 'kendo/hidden.html'
    input_type = 'hidden'

class ComboBoxInput(Input):
    template_name = 'kendo/combobox.html'
    input_type = 'combobox'
