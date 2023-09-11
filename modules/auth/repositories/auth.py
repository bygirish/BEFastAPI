from modules.auth.domain.auth import Auth

fake_users_db = {
    "johndoe1": {
        "user_id": "johndoe1",
        "email_id": "u1@gmail.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
    },
    "johndoe1": {
        "user_id": "johndoe2",
        "email_id": "u2@gmail.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZsdfsfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
    },
    'girish@gmail.com': {'user_id': 'd79dd36b-6ead-4f1d-b977-1c6a9d0cee79', 'email_id': 'girish@gmail.com', 'hashed_password': '$2b$12$OGH9xtnTqB2VqffNyYKLa.rD4RN/TT1fhkDZ5dSN6diQHPTgHgrxu'}
}


def create_user_repository(new_user: Auth):
    # fake_users_db[new_user.email_id] = new_user
    print("new user", new_user)
    fake_users_db.update({
        new_user.email_id: new_user
    })
    print(f"create_user_repository: fake users db {fake_users_db}")


def get_user_by_email_id_repository(email_id: str):
    if email_id in fake_users_db:
        user = fake_users_db[email_id]
        print("user object", user)
        return user
        # return UserInDB(**user_dict)


def get_user_by_user_id_repository(user_id: str):
    if user_id in fake_users_db:
        user_dict = fake_users_db[user_id]
        return user_dict


