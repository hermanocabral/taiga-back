# Copyright (C) 2014 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014 David Barragán <bameda@dbarragan.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.conf import settings

from taiga.projects.history import services as history_services
from taiga.projects.models import Project
from taiga.users.models import User
from taiga.projects.history.choices import HistoryType
from taiga.timeline.service import push_to_timeline

# TODO: Add events to followers timeline when followers are implemented.
# TODO: Add events to project watchers timeline when project watchers are implemented.

def _push_to_timeline(*args, **kwargs):
        if settings.CELERY_ENABLED:
            push_to_timeline.delay(*args, **kwargs)
        else:
            push_to_timeline(*args, **kwargs)


def on_new_history_entry(sender, instance, created, **kwargs):
    if instance.is_hidden:
        return None

    model = history_services.get_model_from_key(instance.key)
    pk = history_services.get_pk_from_key(instance.key)
    obj = model.objects.get(pk=pk)
    if model is Project:
        project = obj
    else:
        project = obj.project

    if instance.type == HistoryType.create:
        event_type = "create"
    elif instance.type == HistoryType.change:
        event_type = "change"
    elif instance.type == HistoryType.delete:
        event_type = "delete"

    extra_data = {
        "values_diff": instance.values_diff,
        "user": instance.user,
        "comment": instance.comment,
    }

    owner = User.objects.get(id=instance.user["pk"])

    _push_to_timeline(project, obj, event_type, extra_data=extra_data)
    _push_to_timeline(owner, obj, event_type, extra_data=extra_data)


def create_membership_push_to_timeline(sender, instance, **kwargs):
    # Creating new membership with associated user
    if not instance.pk and instance.user:
        _push_to_timeline(instance.project, instance, "create")
        _push_to_timeline(instance.user, instance, "create")

    #Updating existing membership
    elif instance.pk:
        prev_instance = sender.objects.get(pk=instance.pk)
        if instance.user != prev_instance.user:
            # The new member
            _push_to_timeline(instance.project, instance, "create")
            _push_to_timeline(instance.user, instance, "create")
            # If we are updating the old user is removed from project
            if prev_instance.user:
                _push_to_timeline(instance.project, prev_instance, "delete")
                _push_to_timeline(prev_instance.user, prev_instance, "delete")


def delete_membership_push_to_timeline(sender, instance, **kwargs):
    _push_to_timeline(instance.project, instance, "delete")
    _push_to_timeline(instance.user, instance, "delete")
