# Email and password sign-in in FastAPI, Cognito later

Users sign in with email and password, handled by the FastAPI backend, which issues a JWT. We chose this over AWS Cognito and Google/Microsoft OAuth because it has no external setup and teaches the mechanics directly. When the AWS phase starts we expect to move to Cognito, so keep auth behind one dependency (`get_current_user`) rather than spreading token checks through the routers.
