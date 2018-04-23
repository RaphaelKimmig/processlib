A workflow/process library for python. WIP

How to display relevant fields from the process model in templates?
Do we have custom templates for certain process models / flows?

How do we handle assignments and permissions?
Who is allowed to undo/cancel tasks?
E.g. the transmit-to-einfachpacken-background-job should not be cancelable by a random user

What happens when we undo a background task that was started automatically?


Questions
------------------------

1. Do we need some kind of "view" permissions for a process / flow?
2. We can have a permission for every activity in a flow, but when do we allow people to view a flow?
3. Should we have "Flow"-Permissions that allow a person to do every step in a flow?
4. How do we deal with flows done by other people, e.g. if we have a flow for creating orders
   they probably should show up only for the one user?


NEXT:

View permissions for different scenarios
--------------------------------------------
1. landing page / order process where we have processes in an inbox and people in a group should
   grab them and get them finished

2. starting some process by going through a multi-step thing where the whole process is just for
   that one user and nobody else should necessarily see it.

Also logging: if some user does a task, do we want to assign it to them in the view?

