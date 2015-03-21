# -*- coding: utf-8 -*-
'''
Created on march 2015

@author: sd-libre
'''

from __future__ import unicode_literals

from django.utils.translation import ugettext as _

from lucterios.framework.tools import icon_path, CLOSE_NO, StubAction, FORMTYPE_REFRESH
from lucterios.framework.xfercomponents import XferCompImage, XferCompLabelForm, XferCompGrid, \
    XferCompSelect, XferCompButton, XferCompFloat, XferCompEdit, XferCompCheck, \
    XferCompDate, XferCompTime, XferCompCheckList
from lucterios.framework.xfergraphic import XferContainerCustom
from django.utils import six

TYPE_FLOAT = 'float'
TYPE_STR = 'str'
TYPE_BOOL = 'bool'
TYPE_DATE = 'date'
TYPE_TIME = 'time'
TYPE_DATETIME = 'datetime'
TYPE_LIST = 'list'
TYPE_LISTMULT = 'listmult'

OP_NULL = ('0', '')
OP_EQUAL = ('1', _('equals'), '__exact')
OP_DIFFERENT = ('2', _("different"), '__iexact')
OP_LESS = ('3', _("inferior"), '__lt')
OP_MORE = ('4', _("superior"), '__gt')
OP_CONTAINS = ('5', _("contains"), '__contains')
OP_STARTBY = ('6', _("starts with"), '__startswith')
OP_ENDBY = ('7', _("ends with"), '__endswith')
OP_OR = ('8', _("or"), '')
OP_AND = ('9', _("and"), '')
OP_LIST = [OP_NULL, OP_EQUAL, OP_DIFFERENT, OP_LESS, OP_MORE, OP_CONTAINS, OP_STARTBY, OP_ENDBY, OP_OR, OP_AND]

LIST_OP_BY_TYPE = {
    TYPE_FLOAT:(OP_EQUAL, OP_DIFFERENT, OP_LESS, OP_MORE,),
    TYPE_STR:(OP_EQUAL, OP_DIFFERENT, OP_CONTAINS, OP_STARTBY, OP_ENDBY),
    TYPE_BOOL:(OP_EQUAL,),
    TYPE_DATE:(OP_EQUAL, OP_DIFFERENT, OP_LESS, OP_MORE,),
    TYPE_TIME:(OP_EQUAL, OP_DIFFERENT, OP_LESS, OP_MORE,),
    TYPE_DATETIME:(OP_EQUAL, OP_DIFFERENT, OP_LESS, OP_MORE,),
    TYPE_LIST:(OP_OR,),
    TYPE_LISTMULT:(OP_OR, OP_AND,),
}

def get_script_for_operator():
    script = "var new_operator='';\n"

    for current_type, op_list in LIST_OP_BY_TYPE.items():
        script += "if (type=='%(type)s') {\n" % {'type':current_type}
        for op_id, op_title, __op_q  in op_list:  # pylint: disable=unused-variable
            script += "    new_operator+='<CASE id=\"%(op_id)s\">%(op_title)s</CASE>';\n" % {'op_id':op_id, 'op_title':op_title}
        script += "}\n"
    script += "parent.get('searchOperator').setValue('<SELECT>'+new_operator+'</SELECT>');\n"
    return script

class FieldDescItem(object):

    def __init__(self, fieldname):
        self.fieldname = fieldname
        self.sub_fieldnames = self.fieldname.split('.')
        self.description = ''
        self.field_type = TYPE_FLOAT
        self.field_list = []

    def _init_for_list(self, sub_model):
        if len(self.sub_fieldnames) == 1:
            self.field_type = TYPE_LIST
            self.field_list = []
            for select_obj in sub_model.objects.all():
                self.field_list.append((six.text_type(select_obj.id), six.text_type(select_obj)))
        else:
            sub_fied_desc = FieldDescItem(".".join(self.sub_fieldnames[1:]))
            sub_fied_desc.init(sub_model._meta.get_field_by_name(self.sub_fieldnames[1])[0]) # pylint: disable=protected-access
            self.description = "%s > %s" % (self.description, sub_fied_desc.description)
            self.field_type = sub_fied_desc.field_type
            self.field_list = sub_fied_desc.field_list

    def init(self, dbfield):
        if self.sub_fieldnames[0][-4:] == '_set':
            self.description = dbfield.model._meta.verbose_name # pylint: disable=protected-access
        else:
            self.description = dbfield.verbose_name
        from django.db.models.fields import IntegerField, FloatField, BooleanField, TextField
        from django.db.models.fields.related import ForeignKey
        if isinstance(dbfield, IntegerField):
            if (dbfield.choices is not None) and (len(dbfield.choices) > 0):
                self.field_type = TYPE_LIST
                self.field_list = []
                for choice_id, choice_val in dbfield.choices:
                    self.field_list.append((six.text_type(choice_id), six.text_type(choice_val)))
            else:
                self.field_type = TYPE_FLOAT
                self.field_list = [(0, 10, 0)]
        elif isinstance(dbfield, FloatField):
            self.field_type = TYPE_FLOAT
            self.field_list = [(0, 10, 2)]
        elif isinstance(dbfield, BooleanField):
            self.field_type = TYPE_BOOL
        elif isinstance(dbfield, TextField):
            self.field_type = TYPE_STR
        elif isinstance(dbfield, ForeignKey):
            sub_model = dbfield.rel.to
            self._init_for_list(sub_model)
        elif hasattr(dbfield, "model"):
            sub_model = dbfield.model
            self._init_for_list(sub_model)
        else:
            self.field_type = TYPE_STR

    def get_list(self):
        # list => 'xxx||yyyy;xxx||yyyy;xxx||yyyy'
        res = []
        for item in self.field_list:
            res.append("||".join(item))
        return ";".join(res)

    def add_from_script(self):
        script_ref = "findFields['" + self.fieldname + "']='" + self.field_type + "';\n"
        if (self.field_type == TYPE_LIST) or (self.field_type == TYPE_LISTMULT) \
            or (self.field_type == TYPE_FLOAT):
            script_ref += "findLists['" + self.fieldname + "']='" + self.get_list() + "';\n"
        return script_ref

    def get_value(self, value, operation):
        if self.field_type == TYPE_STR:
            new_val_txt = '"%s"' % value
        elif self.field_type == TYPE_BOOL:
            if value == 'o':
                new_val_txt = "oui"
            else:
                new_val_txt = "non"
        elif self.field_type == TYPE_DATE:
            new_val_txt = value
        elif self.field_type == TYPE_DATETIME:
            new_val_txt = value
        elif (self.field_type == TYPE_LIST) or (self.field_type == TYPE_LISTMULT):
            new_val_txt = ''
            ids = value.split(';')
            for new_item in self.field_list:
                if new_item[0] in ids:
                    if new_val_txt != '':
                        new_val_txt += ' %s ' % OP_LIST[operation][1]
                    new_val_txt += '"%s"' % new_item[1]
        else:
            new_val_txt = value
        return new_val_txt

    def get_query(self, value, operation):
        if self.field_type == TYPE_BOOL:
            if value == 'o':
                query_txt = "Q(%s=True)" % self.fieldname
            else:
                query_txt = "Q(%s=False)" % self.fieldname
        elif self.field_type == TYPE_FLOAT:
            query_txt = "Q(%s%s=%s)" % (self.fieldname, OP_LIST[operation][2], value)
        elif (self.field_type == TYPE_LIST) or (self.field_type == TYPE_LISTMULT):
            if operation == OP_OR[0]:
                query_txt = "Q(%s__in=%s)" % (self.fieldname, six.text_type(value.split(';')))
            else:
                query_list = []
                for value_item in value.split(';'):
                    query_list.append("Q(%s=%s)" % (self.fieldname, six.text_type(value_item)))
                query_txt = " & ".join(query_list)
        else:
            query_txt = "Q(%s%s='%s')" % (self.fieldname, OP_LIST[operation][2], value)
        return query_txt

    def get_new_criteria(self, params):
        operation = params['searchOperator']
        new_type = self.field_type
        if new_type != '':
            new_val = ''
            if new_type == TYPE_FLOAT:
                new_val = params['searchValueFloat']
            if new_type == TYPE_STR:
                new_val = params['searchValueStr']
            if new_type == TYPE_BOOL:
                new_val = params['searchValueBool']
            if new_type == TYPE_DATE:
                new_val = params['searchValueDate']
            if new_type == TYPE_TIME:
                new_val = params['searchValueTime']
            if new_type == TYPE_DATETIME:
                new_val = params['searchValueDate'] + ' ' + params['searchValueTime']
            if (new_type == TYPE_LIST) or (new_type == TYPE_LISTMULT):
                new_val = params['searchValueList']
            if (new_val != '') or ((new_type == TYPE_STR) and (operation == OP_EQUAL[0])) or ((new_type == TYPE_STR) and (operation == OP_DIFFERENT[0])):
                return [self.fieldname, operation, new_val]
        return None

class FieldDescList(object):

    def __init__(self):
        self.field_desc_list = []

    def initial(self, model):
        self.field_desc_list = []
        for field_name in model.get_fieldnames_for_search():
            field = None
            sub_field_name = field_name.split('.')[0]
            if sub_field_name[-4:] == '_set':  # field is one-to-many relation
                field = getattr(model, sub_field_name)
            else:
                dep_field = model._meta.get_field_by_name(sub_field_name)  # pylint: disable=protected-access
                if dep_field[2]:  # field real in model
                    if not dep_field[3]:  # field not many-to-many
                        field = dep_field[0]
            if field is not None:
                new_field = FieldDescItem(field_name)
                new_field.init(field)
                self.field_desc_list.append(new_field)

    def get_select_and_script(self):
        selector = []
        script_ref = "findFields=new Array();\n"
        script_ref += "findLists=new Array();\n"
        for field_desc_item in self.field_desc_list:
            selector.append((field_desc_item.fieldname, field_desc_item.description))
            script_ref += field_desc_item.add_from_script()
        return selector, script_ref

    def get(self, fieldname):
        for field_desc_item in self.field_desc_list:
            if field_desc_item.fieldname == fieldname:
                return field_desc_item
        return None

class XferSearchEditor(XferContainerCustom):
    filter = None

    def __init__(self):
        XferContainerCustom.__init__(self)
        self.fields_desc = FieldDescList()
        self.criteria_list = []

    def read_criteria_from_params(self):
        criteria = self.getparam('CRITERIA')
        if criteria is not None:
            for criteria_item in criteria.split('//'):
                criteriaval = criteria_item.split('||')
                self.criteria_list.append(criteriaval)
        act_param = self.getparam('ACT')
        if act_param == 'ADD':
            new_name = self.getparam('searchSelector')
            new_criteria = self.fields_desc.get(new_name).get_new_criteria(self.params)
            if new_criteria is not None:
                self.criteria_list.append(new_criteria)
        elif act_param is not None:
            del self.criteria_list[int(self.params['ACT'])]
        temp_list = []
        for criteria_item in self.criteria_list:
            if len(criteria_item) >= 3:
                temp_list.append('||'.join(criteria_item))
        self.params['CRITERIA'] = '//'.join(temp_list)
        if 'ACT' in self.params.keys():
            del self.params['ACT']
        key_list = list(self.params.keys())
        for ctx_key in key_list:
            if ctx_key[0:6] == 'search':
                del self.params[ctx_key]

    def get_text_search(self):
        filter_text_list = []
        criteria_desc = {}
        crit_index = 0
        for criteria_item in self.criteria_list:
            new_name = criteria_item[0]
            if new_name != '':
                new_op = int(criteria_item[1])
                new_val = criteria_item[2]
                field_desc_item = self.fields_desc.get(new_name)
                new_val_txt = field_desc_item.get_value(new_val, new_op)
                filter_text_list.append(field_desc_item.get_query(new_val, new_op))
                if (field_desc_item.field_type == TYPE_LIST) or (field_desc_item.field_type == TYPE_LISTMULT):
                    sep_criteria = OP_EQUAL[1]
                else:
                    sep_criteria = OP_LIST[new_op][1]
                criteria_desc[six.text_type(crit_index)] = "{[b]}%s{[/b]} %s {[i]}%s{[/i]}" % (field_desc_item.description, sep_criteria, new_val_txt)
                crit_index += 1
        if len(filter_text_list) > 0:
            from django.db.models import Q  # pylint: disable=unused-variable
            filter_text = "[%s]" % " & ".join(filter_text_list)
            self.filter = eval(filter_text)  # pylint: disable=eval-used
        else:
            self.filter = []
        return criteria_desc

    def fillresponse_search_select(self):
        selector, script_ref = self.fields_desc.get_select_and_script()
        script_ref += """
var name=current.getValue();
var type=findFields[name];
parent.get('searchValueFloat').setVisible(type=='float');
parent.get('searchValueStr').setVisible(type=='str');
parent.get('searchValueBool').setVisible(type=='bool');
parent.get('searchValueDate').setVisible(type=='date' || type=='datetime');
parent.get('searchValueTime').setVisible(type=='time' || type=='datetime');
parent.get('searchValueList').setVisible(type=='list' || type=='listmult');
"""
        script_ref += get_script_for_operator()
        script_ref += """
if (type=='float') {
    var prec=findLists[name].split(';')
    parent.get('searchValueFloat').setValue('<FLOAT min=\"'+prec[0]+'\" max=\"'+prec[1]+'\" prec=\"'+prec[2]+'\"></FLOAT>')
}
if (type=='str') {
    parent.get('searchValueStr').setValue('<STR></STR>')
}
if (type=='bool') {
    parent.get('searchValueBool').setValue('<BOOL>n</BOOL>')
}
if (type=='date' || type=='datetime') {
    parent.get('searchValueDate').setValue('<DATE>1900/01/01</DATE>')
}
if (type=='time' || type=='datetime') {
    parent.get('searchValueTime').setValue('<DATE>00:00:00</DATE>')
}
if ((type=='list') || (type=='listmult')) {
    var list=findLists[name].split(';')
    var list_txt=''
    for(i=0;i<list.length;i++) {
        var val=list[i].split('||')
        if (val.length>1)
            list_txt+='<CASE id=\"'+val[0]+'\">'+val[1]+'</CASE>'
    }
    parent.get('searchValueList').setValue('<SELECT>'+list_txt+'</SELECT>')
}
"""
        label = XferCompLabelForm('labelsearchSelector')
        label.set_value("{[bold]Nouveau critere{[/bold]")
        label.set_location(0, 1, 1, 7)
        self.add_component(label)
        comp = XferCompSelect("searchSelector")
        comp.set_select(selector)
        comp.set_value("")
        comp.set_location(1, 1, 1, 7)
        comp.set_size(20, 200)
        comp.java_script = script_ref
        self.add_component(comp)
        comp = XferCompSelect("searchOperator")
        comp.set_select({})
        comp.set_value("")
        comp.set_size(20, 200)
        comp.set_location(2, 1, 1, 7)
        self.add_component(comp)

    def fillresponse_search_values(self):
        comp = XferCompButton("searchButtonAdd")
        comp.set_is_mini(True)
        comp.set_location(4, 1, 1, 7)
        comp.set_action(self.request, self.get_changed("", "images/add.png"), {'modal':FORMTYPE_REFRESH, 'close':CLOSE_NO, 'params':{'ACT':'ADD'}})
        self.add_component(comp)

        comp = XferCompDate("searchValueDate")
        comp.set_location(3, 2)
        comp.set_size(20, 200)
        self.add_component(comp)
        comp = XferCompFloat("searchValueFloat")
        comp.set_location(3, 3)
        comp.set_size(20, 200)
        self.add_component(comp)
        comp = XferCompEdit("searchValueStr")
        comp.set_location(3, 4)
        comp.set_size(20, 200)
        self.add_component(comp)
        comp = XferCompCheckList("searchValueList")
        comp.set_location(3, 5)
        comp.set_size(80, 200)
        self.add_component(comp)
        comp = XferCompCheck("searchValueBool")
        comp.set_location(3, 6)
        comp.set_size(20, 200)
        self.add_component(comp)
        comp = XferCompTime("searchValueTime")
        comp.set_location(3, 7)
        comp.set_size(20, 200)
        self.add_component(comp)

        label = XferCompLabelForm('labelsearchSep')
        label.set_value("")
        label.set_size(1, 200)
        label.set_location(3, 8)
        self.add_component(label)

    def fillresponse_show_criteria(self):
        criteria_text_list = self.get_text_search()
        label = XferCompLabelForm('labelsearchDescTitle')
        if len(criteria_text_list) > 0:
            label.set_value_as_info("Your criteria of search")
            label.set_location(0, 8, 2, 4)
        else:
            label.set_value_as_infocenter("No criteria of search")
            label.set_location(0, 8, 4)
        self.add_component(label)

        row = 8
        for criteria_id, criteria_text in criteria_text_list.items():
            label = XferCompLabelForm('labelSearchText_' + criteria_id)
            label.set_value(criteria_text)
            label.set_location(2, row, 2)
            self.add_component(label)
            comp = XferCompButton("searchButtonDel_" + criteria_id)
            comp.set_is_mini(True)
            comp.set_location(4, row)
            comp.set_action(self.request, self.get_changed("", "images/suppr.png"), {'modal':FORMTYPE_REFRESH, 'close':CLOSE_NO, 'params':{'ACT':criteria_id}})
            self.add_component(comp)
            row += 1

    def fillresponse(self):
        # pylint: disable=not-callable
        self.fields_desc.initial(self.item)
        self.read_criteria_from_params()

        img = XferCompImage('img')
        img.set_value(icon_path(self))
        img.set_location(0, 0)
        self.add_component(img)
        lbl = XferCompLabelForm('title')
        lbl.set_value_as_title(self.caption)
        lbl.set_location(1, 0)
        self.add_component(lbl)
        self.fillresponse_search_select()
        self.fillresponse_search_values()
        self.fillresponse_show_criteria()
        row = self.get_max_row()
        if isinstance(self.filter, dict):
            items = self.model.objects.filter(**self.filter)  # pylint: disable=no-member
        elif isinstance(self.filter, list):
            items = self.model.objects.filter(*self.filter)  # pylint: disable=no-member
        else:
            items = self.model.objects.all()  # pylint: disable=no-member
        grid = XferCompGrid(self.field_id)
        grid.set_model(items, None, self)
        grid.add_actions(self)
        grid.set_location(0, row + 4, 4)
        grid.set_size(200, 500)
        self.add_component(grid)
        lbl = XferCompLabelForm("nb")
        lbl.set_location(0, row + 5, 4)
        lbl.set_value(_("Total number of %(name)s: %(count)d") % {'name':self.model._meta.verbose_name_plural, 'count':grid.nb_lines})  # pylint: disable=protected-access
        self.add_component(lbl)

        self.add_action(StubAction(_('Close'), 'images/close.png'), {})