from collections import defaultdict
from contextlib import contextmanager
from django.conf import settings

try:
    from django.forms.utils import ErrorList
except ImportError:
    from django.forms.util import ErrorList

from django.template import (Library, Node, Variable,
                            TemplateSyntaxError,VariableDoesNotExist)
from django.template.base import token_kwargs
from django.utils.functional import empty

from ..compat import get_template
register = Library()

class KendoLanguage():
    def core(self):
        language = '/kendo/js/cultures/kendo.culture.es-MX.min.js'
        messages = '/kendo/js/cultures/kendo.messages.es-MX.min.js'
        return {
        'language' : language,
        'messages' : messages,
        }

class KendoJS():
    def core(self):
        print("entro toda")
        js = '/kendo/js/kendo.core.min.js'
        return js

class KendoStyle():
    def core(self):
        common = '/kendo/style/kendo.common.min.css'
        theme = '/kendo/style/kendo.default.min.css'
        return {
        'common' : common,
        'theme' : theme
        }

def is_formset(var):
    # se dice que es un formset asi que var termina siendo los campos
    significante_attributes = ('forms', 'management_form')
    return all(hasattr(var, attr) for attr in significante_attributes)

def is_form(var):
    # se dice que es un form asi que var termina siendo los campos
    significante_attributes = ('is_bound', 'data', 'fields')
    return all(hasattr(var, attr) for attr in significante_attributes)

def is_bound_field(var):
    # se dice que es un BoundField asi que var termina siendo los campos
    significante_attributes = ('as_widget', 'as_hidden','is_hidden')
    return all(hasattr(var, attr) for attr in significante_attributes)

class ConfigFilter(object):
    '''que conciden con el campo:)
    puede se usado como un filtro para FormConfig.configure() este filtro
    regresara True si:
    *el campo cargado pasa en el constructor equivalente al filtrado
    *el string pasado en el contructor corresponde al nombre del campo
    * "" "" "" equivale a los campos de la clase
    *"" "" "" equivale a los campos del widget'''
    def __init__(self, var):
        self.var = var

    def __call__(self, bound_field):
        #cuando var es un campo llenado
        #campos llevados no pueden ser comparados directos desde form['field'] returns
        # una nueva instancia cada vez que es llamado
        if hasattr(self.var, 'form') and hasattr(self.var, 'name'):
            if self.var.form is bound_field.form:
                if self.var.name == bound_field.name:
                    return True
        if self.var == bound_field.name:
            return True

        for class_ in bound_field.field.__class__.__mro__:
            if class_.__name__ == 'object':
                continue
            if self.var == class_.__name__:
                return True

    def __repr__(self):
        return "<%s: %r>" % (self.__class__.__name__, self.var)

def default_label(bound_field, **kwargs):
    if bound_field:
        return bound_field.label

def default_help_text(bound_field, **kwargs):
    if bound_field:
        return bound_field.helper_text

def default_widget(bound_field, **kwargs):
    if bound_field:
        return bound_field.field.widget

def default_widget_template(bound_field, **kwargs):
    if bound_field:
        if hasattr(bound_field.field.widget, 'template_name'):
            return bound_field.field.widget.template_name
        return None

class ConfigurePopException(Exception):
    "pop() ha sido llamado mas veces que push()"
    pass
class FormConfig(object):
    '''una pila de form-configuration diccionarios, donde por cada
    valor configurado puede ser asociado con una funcion filtro
    que determina como sera utilizado segun la situacion'''
    defaults = {
        'layout' : lambda **kwargs: 'kendo/layouts/default.html',
        'row_template' : lambda **kwargs : 'kendo/rows/default.html',
        'label' : default_label,
        'help_text' :default_help_text,
        'widget': default_widget,
        'widget_template': default_widget_template,
    }

    def __init__(self):
        self.dicts = [self._dict()]

    def _dict(self):
        return defaultdict(lambda: [])

    def push(self):
        d = self._dict()
        self.dicts.append(d)
        return d

    def pop(self):
        if len(self.dicts) == 1:
            raise ConfigPopException
        return self.dicts.pop()

    def configure(self, key, value, filter=None):
        """almacena 'value' bajo 'key', opcionalmente protejido por
        un 'filter'
        """
        if filter is None:
            def filter(**kwargs):
                return True
        self.dicts[-1][key].append((value, filter))

    def retrieve(self,key, **kwargs):
        """regresa most-recently-set para 'key' la cual regresara
        'True' cuando lo pasa el dado **kwargs
        si no se encuentra valor en el 'key' tiene un valor por default
        regresa self.defaults[key](**kwargs)
        """
        for d in reversed(self.dicts):
            for value, filter in reversed(d[key]):
                if filter(**kwargs):
                    return value
        if key not in self.defaults:
            return None
        return self.defaults[key](**kwargs)

    def retrieve_all(self, key, **kwargs):
        """regresa una lista de todos los valores aplicables para 'key'
        ordenado por most-recently-configured
        """
        values = []
        for d in self.dicts:
            for value, filter in d[key]:
                if filter(**kwargs):
                    values.insert(0, value)
        return values

class BaseFormNode(Node):
    """clase base para el rendering del form, mantiene los metodos para
    convertir los argumentos comunes como 'using <template>' en un
    modo estandarizado
    """
    CONFIG_CONTEXT_ATTR = '_form_config'
    IN_FORM_CONTEXT_VAR = '_form_render'

    optional_using_parameter = False
    optional_with_parameter = False
    accept_only_parameter = True
    accept_for_parameter = False
    optional_for_parameter = False
    form_config = FormConfig
    sinple_template_var = None
    list_template_var = None

    def __init__(self, tagname, variables, options):
        self.tagname = tagname
        self.variables = variables
        self.options = options

    def get_config(self, context):
        try:
            return getattr(context, self.CONFIG_CONTEXT_ATTR)
        except AttributeError:
            config = self.form_config()
            setattr(context, self.CONFIG_CONTEXT_ATTR, config)
            return config
    @classmethod
    def parse_variables(cls, tagname, parser, bits, options):
        variables = []
        while bits and bits[0] not in ('using', 'with', 'only'):
            variables.append(Variable(bits.pop()))
        if not variables:
            raise TemplateSyntaxError('%s tag name espera al menos'
                                    'un template como argumento' % tagname)
        return variables

    @classmethod
    def parse_using(cls, tagname, parser, bits, options):
        if bits:
            if bits[0] == 'using':
                bits.pop(0)
                if len(bits):
                    if bits[0] in ('with', 'only'):
                        raise TemplateSyntaxError(
                        '%s: you must provide one template after '
                        '"using" and before "with" or "only".' %
                        tagname
                        )
                    options['using'] = Variable(bits.pop(0))
                else:
                    raise TemplateSyntaxError('%s: expected a template name '
                                              'after "using".' % tagname)
            elif not cls.optional_using_parameter:
                raise TemplateSyntaxError('Unknown argument for %s tag: %r.' %
                                          (tagname, bits[0]))
    @classmethod
    def parse_with(cls, tagname, parser, bits, options):
        if bits:
            if bits[0] == 'with':
                bits.pop[0]
                arguments = token_kwargs(bits, parser, support_legacy=False)
                if not arguments:
                    raise TemplateSyntaxError('"with" in %s tag needs at '
                                              'least one keyword argument.' %
                                              tagname)
                options['with'] = arguments
            elif bits[0] not in ('only',) and not cls.optional_with_parameter:
                raise TemplateSyntaxError('Unknown argument for %s tag: %r.' %
                                          (tagname, bits[0]))
        if bits:
            if cls.accept_only_parameter and vits[0] == 'only':
                bits.pop(0)
                options['only'] = True
    @classmethod
    def parse_for(cls, tagname, parser, bits, options):
        if bits:
            if bits[0] == 'for':
                bits.pop(0)
                if len(bits):
                    options['for'] = Variable(bits.pop(0))
                else:
                    raise TemplateSyntaxError('%s: expected an argument '
                                              'after "for".' % tagname)
            elif not cls.optional_for_parameter:
                raise TemplateSyntaxError('Unknown argument for %s tag: %r.' %
                                          (tagname, bits[0]))
    @classmethod
    def parse(cls, parser, tokens):
        bits = token.split_contents()
        tagname = bits.pop(0)
        options = {
            'only' : False,
            'with' : None,
        }

        variables = cls.parse_variables(tagname, parser, bits, options)
        cls.parse_using(tagname, parser, bits, options)
        cls.parse_with(tagname, parser, bits, options)
        if bits:
            raise TemplateSyntaxError('Unknown argument for %s tag: %r.' %
                                      (tagname, ' '.join(bits)))
        return cls(tagname, variables, options)

class ModifierBase(BaseFormNode):
    """
    Base class for the form modifiers that can be used in the {% formconfig
    <modifier> ... %} tag.
    A modifier is simply yet another template tag that just doesn't get
    registered in a template tag lib. Instead it gets called by the
    ``formconfig`` tag, based on the modifier keyword and gets all the
    remaining arguments.
    Example::
        {% formconfig row using "row.html" %}
    Will call the RowModifier class with the arguments ``using`` and
    ``"row.html"``. See the ``FormConfigNode.parse`` method for more details.
    """
    accept_for_parameter = False
    template_config_name = None
    context_config_name = None

    def __init__(self, tagname, modifier, options):
        self.tagname = tagname
        self.modifier = modifier
        self.options = options

    def enforce_form_tag(self, context):
        if not context.get(self.IN_FORM_CONTEXT_VAR, False):
            raise TemplateSyntaxError('%s debe ser usado dentro de un form tag' %
                                    self.tagname)

    def render(self, context):
        self.enforce_form_tag(context)
        config = self.get_config(context)
        filter = None
        if self.options['for']:
            try:
                for_ = self.options['for'].resolve(context)
            except VariableDoesNotExist:
                if settings.TEMPLATE_DEBUG:
                    raise
                return ''
            filter = ConfigFilter(_for)
        if self.options['using']:
            try:
                template_name = self.options['using'].resolve(context)
            except VariableDoesNotExist:
                if settings.TEMPLATE_DEBUG:
                    raise
                return ''
            config.configure(self.template_config_name,
                            template_name, filter = filter)
        if self.options['with']:
            extra_context = dict([
                (name, var.resolve(context))
                for name, var in self.options['with'].items()])
            config.configure(self.context_config_name,
            extra_context, filter = filter)
        return ''

    @classmethod
    def parse_bits(cls, tagname, modifier, bits, parser, tokens):
        options = {
            'using' : None,
            'with' : None,
            'for' : None,
        }
        if not bits:
            raise TemplateSyntaxError('%s %s: at least one argument '
                                      'is required.' %
                                      (tagname, modifier))
        cls.parse_using(tagname, parser, bits, options)
        cls.parse_with(tagname, parser, bits, options)
        if cls.accept_for_parameter:
            cls.parse_for(tagname, parser, bits, options)

        if bits:
            raise TemplateSyntaxError('Unknown argument for %s %s tag: %r.' %
                                      (tagname, modifier, ' '.join(bits)))


        return cls(tagname, modifier, options)

class RowModifier(ModifierBase):
    """
    {% formconfig row ... %}
    """
    optional_using_parameter = True
    optional_with_parameter = True
    accept_only_parameter = False
    accept_for_parameter = False

    template_config_name = 'row_template'
    context_config_name = 'row_context'

class FieldModifier(ModifierBase):
    """
    {% formconfig field ... %}
    """
    optional_using_parameter = True
    optional_with_parameter = True
    accept_only_parameter = False
    accept_for_parameter = True
    optional_for_parameter = True
    template_config_name = 'widget_template'
    context_config_name = 'widget_context'

class FormConfigNode(BaseFormNode):
    """
    {% formconfig ... %}
    """
    MODIFIERS = {
        'row' : RowModifier,
        'field': FieldModifier
    }

    @classmethod
    def parser(cls, parser, tokens):
        bits = tokens.split_contents()
        tagname = bits.pop(0)
        if not bits or bits[0] not in cls.MODIFIERS:
            raise TemplateSyntaxError(
                '%s needs one of the following keywords as first argument: '
                '%s' % (tagname, ', '.join(cls.MODIFIERS.keys())))
        modifier = bits.pop(0)
        modifier_cls = cls.MODIFIERS[modifier]
        return modifier_cls.parse_bits(tagname, modifier, bits, parser, tokens)

class BaseFormRenderNode(BaseFormNode):
    """
    Base class for ``form``, ``formrow`` and ``formfield`` -- tags that are
    responsible for actually rendering a form and outputting HTML.
    """
    def is_list_variable(self, var):
        return False

    def get_template_name(self, context):
        raise NotImplementedError

    def get_nodelist(self, context, extra_context):
        if 'nodelist' in self.options:
            return self.options['nodelist']
        try:
            if 'using' in self.options:
                template_name = self.options['using'].resolve(context)
            else:
                template_name = self.get_template_name(context)
            return get_template(context, template_name)
        except:
            if settings.TEMPLATE_DEBUG:
                raise

    def get_extra_context(self, context):
        variables = []
        for variable in self.variables:
            try:
                variable = variable.resolve(context)
                if variable is not None:
                    if self.is_list_variable(variable):
                        variables.extend(variable)
                    else:
                        variables.append(variable)
            except VariableDoesNotExist:
                pass

        extra_context = {
            self.single_template_var: variables[0] if variables else None,
        }
        if self.list_template_var:
            extra_context[self.list_template_var] = variables

        if self.options['with']:
            extra_context.update(dict([
                (name, var.resolve(context))
                for name, var in self.options['with'].items()]))

        return extra_context

    def render(self, context):
        only = self.options['only']

        config = self.get_config(context)
        config.push()

        extra_context = self.get_extra_context(context)
        nodelist = self.get_nodelist(context, extra_context)
        if nodelist is None:
            return ''

        if only:
            context = context.new(extra_context)
            output = nodelist.render(context)
        else:
            context.update(extra_context)
            output = nodelist.render(context)
            context.pop()

        config.pop()
        return output


class FormNode(BaseFormRenderNode):
    """
    {% form ... %}
    """
    single_template_var = 'form'
    list_template_var = 'forms'

    def is_list_variable(self, var):
        if not hasattr(var, '__iter__'):
            return False
        if is_formset(var):
                return True
        if is_form(var):
            return False
        # form duck-typing was not successful so it must be a list
        return True

    def get_template_name(self, context):
        config = self.get_config(context)
        return config.retrieve('layout')

    def get_extra_context(self, context):
        extra_context = super(FormNode, self).get_extra_context(context)
        extra_context[self.IN_FORM_CONTEXT_VAR] = True
        return extra_context

    @classmethod
    def parse_using(cls, tagname, parser, bits, options):
        """
        Parses content until ``{% endform %}`` if no template name is
        specified after "using".
        """
        if bits:
            if bits[0] == 'using':
                bits.pop(0)
                if len(bits):
                    if bits[0] in ('with', 'only'):
                        raise TemplateSyntaxError(
                            '%s: you must provide one template after "using" '
                            'and before "with" or "only".')
                    options['using'] = Variable(bits.pop(0))
                else:
                    nodelist = parser.parse(('end%s' % tagname,))
                    parser.delete_first_token()
                    options['nodelist'] = nodelist
            else:
                raise TemplateSyntaxError('Unknown argument for %s tag: %r.' %
                                          (tagname, bits[0]))


class FormRowNode(BaseFormRenderNode):
    """
    {% formrow <bounds fields> ... %}
    """
    single_template_var = 'field'
    list_template_var = 'fields'

    optional_using_parameter = True

    def is_list_variable(self, var):
        if hasattr(var, '__iter__') and not is_bound_field(var):
            return True
        return False

    def get_template_name(self, context):
        config = self.get_config(context)
        return config.retrieve('row_template')

    def get_extra_context(self, context):
        extra_context = super(FormRowNode, self).get_extra_context(context)
        config = self.get_config(context)
        configured_context = {}
        # most recently used values should overwrite older ones
        for extra in reversed(config.retrieve_all('row_context')):
            configured_context.update(extra)
        configured_context.update(extra_context)
        return configured_context


@contextmanager
def attributes(widget, **kwargs):
    old = {}
    for name, value in kwargs.items():
        old[name] = getattr(widget, name, empty)
        setattr(widget, name, value)
    yield widget
    for name, value in old.items():
        if value is not empty:
            setattr(widget, name, value)


class FormFieldNode(BaseFormRenderNode):
    """
    {% formfield <bound field> ... %}
    """
    single_template_var = 'field'
    optional_using_parameter = True

    def get_extra_context(self, context):
        extra_context = super(FormFieldNode, self).get_extra_context(context)
        field = extra_context[self.single_template_var]
        config = self.get_config(context)
        configured_context = {}
        # most recently used values should overwrite older ones
        widget_context = config.retrieve_all('widget_context',
                                             bound_field=field)
        for extra in reversed(widget_context):
            configured_context.update(extra)
        configured_context.update(extra_context)
        return configured_context

    def render(self, context):
        config = self.get_config(context)

        assert len(self.variables) == 1
        try:
            bound_field = self.variables[0].resolve(context)
        except VariableDoesNotExist:
            if settings.DEBUG:
                raise
            return ''

        widget = config.retrieve('widget', bound_field=bound_field)
        extra_context = self.get_extra_context(context)
        template_name = config.retrieve('widget_template',
                                        bound_field=bound_field)
        if 'using' in self.options:
            try:
                template_name = self.options['using'].resolve(context)
            except VariableDoesNotExist:
                if settings.DEBUG:
                    raise
                return ''

        if self.options['only']:
            context_instance = context.new(extra_context)
        else:
            context.update(extra_context)
            context_instance = context

        config.push()

        # Using a context manager here until Django's BoundField takes
        # template name and context instance parameters
        with attributes(widget, template_name=template_name,
                        context_instance=context_instance) as widget:
            output = bound_field.as_widget(widget=widget)

        config.pop()

        if not self.options['only']:
            context.pop()

        if bound_field.field.show_hidden_initial:
            return output + bound_field.as_hidden(only_initial=True)
        return output

    @classmethod
    def parse_variables(cls, tagname, parser, bits, options):
        variables = []
        while bits and bits[0] not in ('using', 'with', 'only'):
            variables.append(Variable(bits.pop(0)))
        if len(variables) != 1:
            raise TemplateSyntaxError('%s tag expectes exactly one '
                                      'template variable as argument.' %
                                      tagname)
        return variables


class WidgetNode(Node):
    """A template tag for rendering a widget with the outer context available.
    This is useful for for instance for using floppyforms with
    django-sekizai."""

    def __init__(self, field):
        self.field = Variable(field)

    def render(self, context):
        field = self.field.resolve(context)

        if callable(getattr(field.field.widget, 'get_context', None)):
            name = field.html_name
            attrs = {'id': field.auto_id}
            value =  field.value()
            widget_ctx = field.field.widget.get_context(name, value, attrs)
            template = field.field.widget.template_name
        else:
            widget_ctx = {'field': field}
            template = 'kendo/dummy.html'

        template = get_template(context, template)
        context.update(widget_ctx)
        rendered = template.render(context)
        context.pop()
        return rendered

    @classmethod
    def parse(cls, parser, tokens):
        print 'WidgetNode'
        bits = tokens.split_contents()
        if len(bits) != 2:
            raise TemplateSyntaxError("{% widget %} takes one and only one argument")
        field = bits.pop(1)
        return cls(field)


@register.filter
def hidden_field_errors(form):
    hidden_field_errors = ErrorList()
    for field in form.hidden_fields():
        hidden_field_errors.extend(field.errors)
    return hidden_field_errors


@register.filter
def id(bound_field):
    widget = bound_field.field.widget
    for_id = widget.attrs.get('id') or bound_field.auto_id
    if for_id:
        for_id = widget.id_for_label(for_id)
    return for_id


register.tag('kendojs', KendoJS.core)
register.tag('kendolanguage', KendoLanguage.core)
register.tag('kendostyle', KendoStyle.core)
register.tag('formconfig', FormConfigNode.parse)
register.tag('form', FormNode.parse)
register.tag('formrow', FormRowNode.parse)
register.tag('formfield', FormFieldNode.parse)
register.tag('widget', WidgetNode.parse)
