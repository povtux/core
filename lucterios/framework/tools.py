# -*- coding: utf-8 -*-
'''
General tools for Lucterios

@author: Laurent GAY
@organization: sd-libre.fr
@contact: info@sd-libre.fr
@copyright: 2015 sd-libre.fr
@license: This file is part of Lucterios.

Lucterios is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Lucterios is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Lucterios.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import unicode_literals
from datetime import datetime
from calendar import monthrange

from django.utils import six
from django.utils.translation import ugettext_lazy as _

from lxml import etree
import threading
import logging

CLOSE_NO = 0
CLOSE_YES = 1
FORMTYPE_NOMODAL = 0
FORMTYPE_MODAL = 1
FORMTYPE_REFRESH = 2
SELECT_NONE = 1
SELECT_SINGLE = 0
SELECT_MULTI = 2

bad_permission_redirect_classaction = None


def get_icon_path(icon_path, url_text='', extension=''):
    from django.conf import settings
    res_icon_path = ""
    if (icon_path is not None) and (icon_path != ""):
        if url_text.find('/') != -1:
            extension = url_text.split('/')[0]
        if icon_path.startswith(settings.STATIC_URL):
            res_icon_path = icon_path
        elif icon_path.startswith('images/'):
            res_icon_path = "%slucterios.CORE/%s" % (
                settings.STATIC_URL, icon_path)
        elif ('images/' in icon_path):
            res_icon_path = "%s%s" % (settings.STATIC_URL, icon_path)
        elif (extension == '') or (extension == 'CORE'):
            res_icon_path = "%slucterios.CORE/images/%s" % (
                settings.STATIC_URL, icon_path)
        else:
            res_icon_path = "%s%s/images/%s" % (
                settings.STATIC_URL, extension, icon_path)
    return res_icon_path


class WrapAction(object):

    mode_connect_notfree = None

    def __init__(self, caption, icon_path, extension='', action='', url_text='', pos=0, is_view_right=''):
        self.caption = caption
        self.icon_path = get_icon_path(icon_path, url_text, extension)
        self.modal = FORMTYPE_MODAL
        self.is_view_right = is_view_right
        self.url_text = url_text
        if (extension == '') and (action == '') and (url_text.find('/') != -1):
            self.extension, self.action = url_text.split('/')
        else:
            self.extension = extension
            self.action = action
        self.pos = pos

    def get_action_xml(self, option, desc='', tag='ACTION'):
        actionxml = etree.Element(tag)
        actionxml.text = six.text_type(self.caption)
        actionxml.attrib['id'] = self.url_text
        if self.icon_path != "":
            actionxml.attrib['icon'] = six.text_type(self.icon_path)
        if self.extension != "":
            actionxml.attrib['extension'] = self.extension
        if self.action != "":
            actionxml.attrib['action'] = self.action
        if desc != "":
            etree.SubElement(actionxml, "HELP").text = six.text_type(desc)
        actionxml.attrib['modal'] = six.text_type(FORMTYPE_MODAL)
        actionxml.attrib['close'] = six.text_type(CLOSE_YES)
        actionxml.attrib['unique'] = six.text_type(SELECT_NONE)
        if isinstance(self.modal, int):
            actionxml.attrib['modal'] = six.text_type(self.modal)
        if 'params' in option:
            fill_param_xml(actionxml, option['params'])
            del option['params']
        for key in option.keys():  # modal, close, unique
            if isinstance(option[key], six.integer_types):
                actionxml.attrib[key] = six.text_type(option[key])
        return actionxml

    def check_permission(self, request):
        right_result = True
        if isinstance(self.is_view_right, tuple):
            view_right_fct = self.is_view_right[0]
            right_result = view_right_fct(request)
        elif self.is_view_right is None:
            right_result = request.user.is_authenticated()
        elif self.mode_connect_notfree is None or self.mode_connect_notfree():
            if (self.is_view_right != '') and not request.user.has_perm(self.is_view_right):
                right_result = False
            if (self.caption == '') and not request.user.is_authenticated():
                right_result = False
        logging.getLogger("lucterios.core.right").info(
            "check_permission for '%s' : is_view_right='%s' user='%s' => '%s'", self.url_text, self.is_view_right, request.user, right_result)
        return right_result

    def raise_bad_permission(self, request):
        if not self.check_permission(request):
            from lucterios.framework.error import LucteriosRedirectException
            if request.user.is_authenticated():
                username = request.user.username
            else:
                username = _("Anonymous user")
            raise LucteriosRedirectException(
                _("Bad permission for '%s'") % username, bad_permission_redirect_classaction)

    @classmethod
    def is_permission(cls, request, is_view_right):
        return cls(caption='', icon_path='', is_view_right=is_view_right).check_permission(request)


class ActionsManage(object):

    _VIEW_LIST = {}

    _actlock = threading.RLock()

    @classmethod
    def affect(cls, *arg_tuples):
        def wrapper(item):
            cls._actlock.acquire()
            try:
                model_name = arg_tuples[0]
                action_types = arg_tuples[1:]
                for action_type in action_types:
                    ident = "%s@%s" % (model_name, action_type)
                    cls._VIEW_LIST[ident] = item
                    logging.getLogger("lucterios.core.action").debug(
                        "new affection: %s", ident)
                return item
            finally:
                cls._actlock.release()
        return wrapper

    @classmethod
    def get_act_changed(cls, model_name, action_type, title, icon):
        cls._actlock.acquire()
        try:
            ident = "%s@%s" % (model_name, action_type)
            if ident in cls._VIEW_LIST.keys():
                view_class = cls._VIEW_LIST[ident]
                return view_class.get_action(title, icon)
            else:
                return None
        finally:
            cls._actlock.release()


class MenuManage(object):

    _MENU_LIST = {}

    _menulock = threading.RLock()

    @classmethod
    def add_sub(cls, ref, parentref, icon, caption, desc, pos=0):
        from django.conf import settings
        cls._menulock.acquire()
        try:
            if icon.startswith('images/'):
                icon_path = "%slucterios.CORE/%s" % (settings.STATIC_URL, icon)
            elif 'images/' in icon:
                icon_path = "%s%s" % (settings.STATIC_URL, icon)
            else:
                icon_path = icon
            if parentref not in cls._MENU_LIST.keys():
                cls._MENU_LIST[parentref] = []
            add_new_menu = True
            for old_menu in cls._MENU_LIST[parentref]:
                if old_menu[0].url_text == ref:
                    add_new_menu = False
            if add_new_menu:
                logging.getLogger("lucterios.core.menu").debug(
                    "new sub-menu: caption=%s ref=%s", caption, ref)
                cls._MENU_LIST[parentref].append(
                    (WrapAction(caption, icon_path, url_text=ref, pos=pos), desc))
        finally:
            cls._menulock.release()

    @classmethod
    def describ(cls, right, modal=FORMTYPE_MODAL, menu_parent=None, menu_desc=None):
        def wrapper(item):
            cls._menulock.acquire()
            try:
                item.initclass(right)
                if menu_parent is not None:
                    if menu_parent not in cls._MENU_LIST.keys():
                        cls._MENU_LIST[menu_parent] = []
                    logging.getLogger("lucterios.core.menu").debug(
                        "new menu: caption=%s ref=%s", item.caption, item.url_text)
                    cls._MENU_LIST[menu_parent].append(
                        (item.get_action(item.caption, item.icon_path(), modal=modal), menu_desc))
                return item
            finally:
                cls._menulock.release()
        return wrapper

    @classmethod
    def fill(cls, request, parentref, parentxml):
        def menu_key_to_comp(menu_item):
            try:
                return menu_item[0].pos
            except AttributeError:
                return 0
        cls._menulock.acquire()
        try:
            if parentref in cls._MENU_LIST.keys():
                sub_menus = cls._MENU_LIST[parentref]
                sub_menus.sort(key=menu_key_to_comp)
                for sub_menu_item in sub_menus:
                    if sub_menu_item[0].check_permission(request):
                        new_xml = sub_menu_item[0].get_action_xml(
                            {}, sub_menu_item[1], "MENU")
                        if new_xml is not None:
                            parentxml.append(new_xml)
                            cls.fill(
                                request, sub_menu_item[0].url_text, new_xml)
        finally:
            cls._menulock.release()


def get_actions_xml(actions):
    actionsxml = etree.Element("ACTIONS")
    for (action, options) in actions:
        new_xml = action.get_action_xml(options)
        if new_xml is not None:
            actionsxml.append(new_xml)
    return actionsxml


def fill_param_xml(context, params):
    for key, value in params.items():
        new_param = etree.SubElement(context, 'PARAM')
        if isinstance(value, tuple) or isinstance(value, list):
            new_param.text = ";".join(value)
        else:
            new_param.text = six.text_type(value)
        new_param.attrib['name'] = key


def ifplural(count, test_singular, test_plural):
    if count == 1:
        return test_singular
    else:
        return test_plural


def get_corrected_setquery(setquery):
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    if setquery.model == Permission:
        ctypes = ContentType.objects.all()
        for ctype in ctypes:
            if ctype.model in ('contenttype', 'logentry', 'permission'):
                setquery = setquery.exclude(
                    content_type=ctype, codename__startswith='add_')
                setquery = setquery.exclude(
                    content_type=ctype, codename__startswith='change_')
                setquery = setquery.exclude(
                    content_type=ctype, codename__startswith='delete_')
            if ctype.model in ('session',):
                setquery = setquery.exclude(
                    content_type=ctype, codename__startswith='add_')
    return setquery


def get_dico_from_setquery(setquery):
    from django.contrib.auth.models import Permission
    res_dico = {}
    if setquery.model == Permission:
        for record in setquery:
            rigths = six.text_type(record.codename).split("_")
            if rigths[0] not in ['add', 'change', 'delete']:
                res_dico[six.text_type(record.id)] = six.text_type(
                    _(record.name))
            else:
                if rigths[0] == 'add':
                    rigth_name = _('add')
                elif rigths[0] == 'change':
                    rigth_name = _('view')
                elif rigths[0] == 'delete':
                    rigth_name = _('delete')
                res_dico[six.text_type(record.id)] = "%s | %s %s" % (
                    six.text_type(record.content_type), _("Can"), rigth_name)
    else:
        for record in setquery:
            res_dico[six.text_type(record.id)] = six.text_type(record)
    return res_dico


def get_binay(text):
    if six.PY2:
        return six.binary_type(text)
    else:
        return six.binary_type(text, 'ascii')


def toHtml(text):
    text = six.text_type(text)
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('{[newline]}', '<br/>')
    text = text.replace('{[bold]}', '<b>')
    text = text.replace('{[/bold]}', '</b>')
    text = text.replace('{[italic]}', '<i>')
    text = text.replace('{[/italic]}', '</i>')
    text = text.replace('{[underline]}', '<u>')
    text = text.replace('{[/underline]}', '</u>')
    text = text.replace('{[', '<')
    text = text.replace(']}', '>')
    text = text.replace('& ', '&amp; ')
    return text


def convert_date(current_date, defaultdate=None):
    try:
        return datetime.strptime(current_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return defaultdate


def same_day_months_after(start_date, months=1):
    month_val = start_date.month - 1 + months
    if month_val < 0:
        target_year = start_date.year + int(month_val / 12) - 1
    else:
        target_year = start_date.year + int(month_val / 12)
    target_month = month_val % 12 + 1
    num_days_target_month = monthrange(target_year, target_month)[1]
    return start_date.replace(year=target_year, month=target_month, day=min(start_date.day, num_days_target_month))
