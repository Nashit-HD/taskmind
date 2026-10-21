# Chats are private to one User and scoped to one Note

Every Chat belongs to exactly one Note and one User; other Users cannot see it, and there are no free-standing Chats. The Assistant reads only that Chat's Note when answering. We considered one shared Chat per Note and letting the Assistant search all Notes, and rejected both: private Chats keep each person's questions their own, and a single-Note scope keeps answers grounded and stops content from other Notes leaking in. Deleting a Note deletes its Chats and their Messages.
