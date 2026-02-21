from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
import uuid

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # 既存ユーザーがいる場合は何もしない（SOCIALACCOUNT_EMAIL_AUTHENTICATION が処理する）
        if sociallogin.is_existing:
            return

        # 念のため、メールアドレスが未設定でも進めるようにする
        if not sociallogin.email_addresses:
            # 基本的に Google ログインではあり得ないが、ガードとして
            pass

    def is_auto_signup_allowed(self, request, sociallogin):
        # False を返すと、SOCIALACCOUNT_AUTO_SIGNUP = False の時にサインアップ画面が表示される
        return False

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        # ユーザー名が空、または衝突を避けるためにユニークな値をセット
        if not user.username or len(user.username) < 2:
            email_part = user.email.split('@')[0] if user.email else "user"
            user.username = f"{email_part}_{uuid.uuid4().hex[:6]}"
        return user
