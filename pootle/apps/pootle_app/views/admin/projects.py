# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView

from pootle.core.delegate import formats
from pootle.core.views import APIView
from pootle.i18n.gettext import ugettext as _
from pootle_app.forms import ProjectForm
from pootle_config.utils import ObjectConfig
from pootle_fs.delegate import fs_plugins
from pootle_fs.presets import FS_PRESETS
from pootle_language.models import Language
from pootle_project.models import PROJECT_CHECKERS, Project


__all__ = ('ProjectAdminView', 'ProjectAPIView')


class ProjectCreationRequiredMixin(object):
    """Require users to be allowed to create projects.

    Superusers always are, other users need the `create_project`
    permission on the root directory.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.can_create_projects:
            msg = _('You do not have rights to create projects in Pootle.')
            raise PermissionDenied(msg)

        return super(ProjectCreationRequiredMixin, self).dispatch(
            request, *args, **kwargs)


class ProjectAdminView(ProjectCreationRequiredMixin, TemplateView):
    template_name = 'admin/projects.html'

    def get_context_data(self, **kwargs):
        languages = Language.objects.exclude(code='templates')
        language_choices = [(lang.id, unicode(lang)) for lang in languages]
        try:
            english = Language.objects.get(code='en')
            default_language = english.id
        except Language.DoesNotExist:
            default_language = languages[0].id

        filetypes = []
        for info in formats.get().values():
            filetypes.append(
                [info["pk"], info["display_title"]])

        project_checker_choices = [
            (checker, checker)
            for checker
            in sorted(PROJECT_CHECKERS.keys())]
        plugin_choices = sorted([(x, x) for x in fs_plugins.gather()])
        fs_presets = FS_PRESETS.values()
        return {
            'page': 'admin-projects',
            'form_choices': {
                'checkstyle': project_checker_choices,
                'filetypes': filetypes,
                'fs_plugin': plugin_choices,
                'fs_preset': fs_presets,
                'source_language': language_choices,
                'defaults': {
                    'source_language': default_language,
                },
            },
        }


class ProjectAPIView(ProjectCreationRequiredMixin, APIView):
    model = Project
    base_queryset = Project.objects.order_by('-id')
    add_form_class = ProjectForm
    edit_form_class = ProjectForm
    page_size = 10
    search_fields = ('code', 'fullname', 'disabled')
    m2m = ("filetypes", )
    config = (
        ("fs_plugin", "pootle_fs.fs_type"),
        ("fs_url", "pootle_fs.fs_url"),
        ("fs_mapping", "pootle_fs.translation_mappings"))

    def serialize_config(self, info, item):
        config = ObjectConfig(item)
        for k, v in self.config:
            if k == "fs_mapping":
                mapping = config.get(v) or {}
                info[k] = mapping.get("default")
            else:
                info[k] = config.get(v)
        info["template_name"] = (
            item.lang_mapper.get_upstream_code("templates"))

    def dispatch(self, request, *args, **kwargs):
        # The `create_project` permission only grants project creation, so
        # non superusers can neither see nor alter the existing projects.
        if not request.user.is_superuser:
            method = request.method.upper()
            if method in ('PUT', 'DELETE'):
                msg = _('You do not have rights to administer Pootle.')
                raise PermissionDenied(msg)
            if method == 'GET':
                self.base_queryset = Project.objects.none()

        return super(ProjectAPIView, self).dispatch(request, *args, **kwargs)
