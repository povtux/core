# -*- coding: utf-8 -*-
'''
Advance abstract viewer classes for Lucterios

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
from logging import getLogger
from copy import deepcopy

from django.utils.translation import ugettext as _, ugettext_lazy
from django.db import IntegrityError
from django.db.models import Q
from django.utils import six

from lucterios.framework.error import LucteriosException, GRAVE, IMPORTANT
from lucterios.framework.tools import ifplural, CLOSE_NO, WrapAction, ActionsManage, CLOSE_YES
from lucterios.framework.xfercomponents import XferCompImage, XferCompLabelForm, XferCompGrid,\
    DEFAULT_ACTION_LIST
from lucterios.framework.xfergraphic import XferContainerAcknowledge, XferContainerCustom


class XferListEditor(XferContainerCustom):
    multi_page = True

    def __init__(self, **kwargs):
        XferContainerCustom.__init__(self, **kwargs)
        self.fieldnames = None
        self.action_list = [('listing', ugettext_lazy("Listing"), "images/print.png"),
                            ('label', ugettext_lazy("Label"), "images/print.png")]
        self.action_grid = deepcopy(DEFAULT_ACTION_LIST)
        self.filter = None

    def fillresponse_header(self):
        return

    def get_items_from_filter(self):
        if isinstance(self.filter, Q) and (len(self.filter.children) > 0):
            items = self.model.objects.filter(
                self.filter)
        else:
            items = self.model.objects.all()
        return items

    def fill_grid(self, row, model, field_id, items):
        grid = XferCompGrid(field_id)
        if self.multi_page:
            xfer = self
        else:
            xfer = None
        grid.set_model(items, self.fieldnames, xfer)
        grid.add_actions(self, action_list=self.action_grid, model=model)
        grid.set_location(0, row + 1, 2)
        grid.set_size(200, 500)
        self.add_component(grid)
        lbl = XferCompLabelForm("nb_" + field_id)
        lbl.set_location(0, row + 2, 2)
        lbl.set_value(_("Total number of %(name)s: %(count)d") % {
                      'name': model._meta.verbose_name_plural, 'count': grid.nb_lines})
        self.add_component(lbl)

    def fillresponse_body(self):
        self.items = self.get_items_from_filter()
        self.fill_grid(
            self.get_max_row(), self.model, self.field_id, self.items)

    def fillresponse(self):
        img = XferCompImage('img')
        img.set_value(self.icon_path())
        img.set_location(0, 0)
        self.add_component(img)
        lbl = XferCompLabelForm('title')
        lbl.set_value_as_title(self.caption)
        lbl.set_location(1, 0)
        self.add_component(lbl)
        self.fillresponse_header()
        self.fillresponse_body()
        if self.model is not None:
            for act_type, title, icon in self.action_list:
                self.add_action(ActionsManage.get_act_changed(
                    self.model.__name__, act_type, title, icon), {'close': CLOSE_NO})
        self.add_action(WrapAction(_('Close'), 'images/close.png'), {})


class XferAddEditor(XferContainerCustom):
    caption_add = ''
    caption_modify = ''
    redirect_to_show = 'show'
    locked = True

    def fillresponse(self):
        if self.is_new:
            self.caption = self.caption_add
        else:
            self.caption = self.caption_modify
        img = XferCompImage('img')
        img.set_value(self.icon_path())
        img.set_location(0, 0, 1, 6)
        self.add_component(img)
        self.fill_from_model(1, 0, False)
        if len(self.actions) == 0:
            self.add_action(
                self.get_action(_('Ok'), 'images/ok.png'), {'params': {"SAVE": "YES"}})
            self.add_action(WrapAction(_('Cancel'), 'images/cancel.png'), {})

    def get(self, request, *args, **kwargs):
        getLogger("lucterios.core.request").debug(
            ">> get %s [%s]", request.path, request.user)
        try:
            self._initialize(request, *args, **kwargs)
            if self.getparam("SAVE") != "YES":
                self.fillresponse()
                self._finalize()
                return self.get_response()
            else:
                return self.run_save(request, *args, **kwargs)
        finally:
            getLogger("lucterios.core.request").debug(
                "<< get %s [%s]", request.path, request.user)

    def run_save(self, request, *args, **kwargs):
        save = XferSave()
        save.is_view_right = self.is_view_right
        save.locked = self.locked
        save.model = self.model
        save.field_id = self.field_id
        save.caption = self.caption
        save.raise_except_class = self.__class__
        save.closeaction = self.closeaction
        save.redirect_to_show = self.redirect_to_show
        return save.get(request, *args, **kwargs)


class XferShowEditor(XferContainerCustom):

    locked = True
    readonly = True

    def __init__(self, **kwargs):
        XferContainerCustom.__init__(self, **kwargs)
        self.action_list = [('modify', _("Modify"), "images/edit.png", CLOSE_YES),
                            ('print', _("Print"), "images/print.png", CLOSE_NO)]

    def fillresponse(self):
        max_row = self.get_max_row() + 1
        img = XferCompImage('img')
        img.set_value(self.icon_path())
        img.set_location(0, 0, 1, 6)
        self.add_component(img)
        self.fill_from_model(1, max_row, True)
        for action_item in self.action_list:
            act_type, title, icon, close = action_item[:4]
            if len(action_item) > 4:
                params = action_item[4]
            else:
                params = {}
            self.add_action(ActionsManage.get_act_changed(
                self.model.__name__, act_type, title, icon), {'close': close, 'params': params})
        self.add_action(WrapAction(_('Close'), 'images/close.png'), {})


class XferDelete(XferContainerAcknowledge):

    def _search_model(self):
        if self.model is None:
            raise LucteriosException(GRAVE, _("No model"))
        if isinstance(self.field_id, tuple):
            for field_id in self.field_id:
                ids = self.getparam(field_id)
                if ids is not None:
                    self.field_id = field_id
                    break
        else:
            ids = self.getparam(self.field_id)
        if ids is None:
            raise LucteriosException(GRAVE, _("No selection"))
        ids = ids.split(';')
        self.items = self.model.objects.filter(pk__in=ids)

    def fillresponse(self):

        for item in self.items:
            cant_del_msg = item.get_final_child().can_delete()
            if cant_del_msg != '':
                raise LucteriosException(IMPORTANT, cant_del_msg)

        if self.confirme(ifplural(len(self.items), _("Do you want delete this %(name)s ?") % {'name': self.model._meta.verbose_name},
                                  _("Do you want delete those %(nb)s %(name)s ?") % {'nb': len(self.items), 'name': self.model._meta.verbose_name_plural})):
            for item in self.items:
                item.get_final_child().delete()


class XferSave(XferContainerAcknowledge):
    raise_except_class = None
    redirect_to_show = 'show'

    def fillresponse(self):
        if "SAVE" in self.params.keys():
            del self.params["SAVE"]
        if self.has_changed:
            self.item.editor.before_save(self)
            try:
                self.item.save()
                self.has_changed = False
                if self.fill_manytomany_fields():
                    self.item.save()
            except IntegrityError as err:
                getLogger("lucterios.core.container").info("%s", err)
                six.print_(err)
                self.raise_except(
                    _("This record exists yet!"), self.raise_except_class)
        if self.except_msg == '':
            self.item.editor.saving(self)
        if isinstance(self.redirect_to_show, six.text_type):
            self.redirect_action(ActionsManage.get_act_changed(
                self.model.__name__, self.redirect_to_show, '', ''), {'params': {self.field_id: self.item.id}})
