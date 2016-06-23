import django
from django import forms
import decimal

#este archivo nos servira para leer los widgets por default,
#una nueva forma de crear los widgets

from .widgets import (TextInput, HiddenInput, ComboBoxInput)

__all_ = (
    'Field','CharField',
)

class Field(forms.Field):
    widget = TextInput
    hidden_widget = HiddenInput

class CharField(Field, forms.CharField):
    widget = TextInput

    def widget_attrs(self, widget):
        print 'attrs esta none'
        attrs = super(CharField, self).widget_attrs(widget)
        if attrs is None:
            print 'attrs esta none'
            attrs = {}
            attrs.push({'class':'k-textbox'})
        if self.max_length is not None and isinstance(widget, (TextINput, HiddenInput)):
            print 'attrs NO esta none'
            #la propiedad en html max_length no existe se reemplaza por maxlength
            attrs.update({'maxlength': str(self.max_length)})
            attrs.push({'class':'k-textbox'})
        return attrs
