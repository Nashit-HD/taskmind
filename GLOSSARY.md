# TaskMind

A shared notebook where signed-in people write notes for everyone to read, and anyone can ask questions about a note in a private chat that an assistant answers from that note.

## People

**User**:
A person who has signed in to TaskMind.
_Avoid_: Account, member, customer

**Author**:
The User who created a given Note. Only the Author may change or remove it.
_Avoid_: Owner, creator, writer

## Content

**Note**:
A titled piece of text written by an Author and readable by every User.
_Avoid_: Document, memo, page, file

## Asking about a note

**Chat**:
A private series of Messages between one User and the Assistant about exactly one Note.
_Avoid_: Conversation, thread, room, session

**Message**:
A single entry in a Chat, written either by the User or by the Assistant. Once sent it never changes.
_Avoid_: Post, reply, comment

**Assistant**:
The AI agent that answers a User's questions in a Chat, using only that Chat's Note.
_Avoid_: Bot, AI, agent, model
