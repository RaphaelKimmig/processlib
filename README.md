A workflow/process library for python. WIP

How to display relevant fields from the process model in templates?
Do we have custom templates for certain process models / flows?

How do we handle assignments and permissions?
Who is allowed to undo/cancel tasks?
E.g. the transmit-to-einfachpacken-background-job should not be cancelable by a random user

What happens when we undo a background task that was started automatically?


ISSUES
---------------
- If some user does a task, do we want to assign it to them in the view?
  Do we offer any way to track who did which activity?
- Right now undoing or canceling activities may result in undesirable states.
  If, for example, all activities in a process are canceled they will no longer
  show up as current processes for **any** user while not being finished either.
  Also the split of undo and cancel into separate tasks may be to complicated
  for users to handle. The most common use case may be canceling the successor to
  undo a previous activity, so maybe we should just offer an `undo`-button for the
  previous activity and handle cancellation of successors from there.



Permissions
----------

You can have permissions for flows or for single activities. Having the flow permissions
grants permissions to all activities in the flow.

Views that are only concerned with a single process or activity (e.g. everything that
uses `ActivityMixin` or the `ProcessDetailView`) will validate flow permissions automatically.

Due to performance limitations, the list views and services **will not validate permissions**
by default.

Defining a permission for a flow means that all users that want to do activities in that flow
 require the flow permission.

Defining a permission for an activity requires that the user has the permission for that specific
 activity in order to do it.

Viewing the details of a process requires that the user have either the permission for the whole
flow (if any such permission is defined) or the permission for any of the activities in the flow.

