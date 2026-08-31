"""API ViewSets for accounts app."""
import logging
import os

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib.auth import (
    SESSION_KEY,
    authenticate,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.models import User
from accounts.permissions import OpenSignupAllowed
from accounts.serializers import UserSerializer
from accounts.throttles import (
    ChangePasswordRateThrottle,
    LoginEmailRateThrottle,
    LoginIPRateThrottle,
    PasswordResetRequestThrottle,
    SignupRateThrottle,
)
from accounts.tokens import get_impersonation_token
from core.file_validation import validate_upload, ALLOWED_IMAGE_TYPES, AVATAR_MAX_SIZE


class AuthViewSet(viewsets.ViewSet):
    """ViewSet for session-based authentication endpoints."""

    def get_permissions(self):
        if self.action in {"login", "password_reset", "password_reset_confirm"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(
        detail=False,
        methods=["post"],
        url_path="login",
        throttle_classes=[LoginIPRateThrottle, LoginEmailRateThrottle],
    )
    def login(self, request):
        """Login endpoint that creates a Django authenticated session."""
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"detail": _("Email and password are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request=request, username=email, password=password)
        if user is None:
            return Response({"detail": _("Invalid credentials.")}, status=status.HTTP_401_UNAUTHORIZED)

        auth_login(request, user)
        return Response(
            {
                "detail": _("Login successful."),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        """Logout endpoint that clears the Django authenticated session."""
        auth_logout(request)
        return Response({"detail": _("Logout successful.")}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="password-reset",
        throttle_classes=[PasswordResetRequestThrottle],
    )
    def password_reset(self, request):
        """Request a password reset email.

        POST /api/accounts/auth/password-reset/
        Body: { email }

        Always returns 200 — never reveals whether the email exists in the database.
        If a user with that email exists, an email is sent with a reset link.
        """
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response(
                {"detail": _("Email is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            user = None

        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"

            context = {"user": user, "reset_url": reset_url}
            text_body = render_to_string("accounts/emails/password_reset.txt", context)
            html_body = render_to_string("accounts/emails/password_reset.html", context)

            message = EmailMultiAlternatives(
                subject=str(_("Reset your Maisonnée password")),
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            message.attach_alternative(html_body, "text/html")
            message.send(fail_silently=False)
            logger.info("Password reset email sent to user_id=%s", user.id)

        return Response(
            {"detail": _("If an account with that email exists, a reset link has been sent.")},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="password-reset/confirm",
    )
    def password_reset_confirm(self, request):
        """Confirm a password reset with token + new password.

        POST /api/accounts/auth/password-reset/confirm/
        Body: { uid, token, new_password }
        """
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        new_password = request.data.get("new_password", "")

        if not uid or not token or not new_password:
            return Response(
                {"detail": _("uid, token and new_password are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": _("Invalid or expired reset link.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": _("Invalid or expired reset link.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            return Response(
                {"detail": " ".join(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])
        logger.info("Password reset completed for user_id=%s", user.id)
        return Response(
            {"detail": _("Password has been reset successfully.")},
            status=status.HTTP_200_OK,
        )


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for user CRUD operations."""
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        if user.is_staff:
            return User.objects.all().order_by("id")
        return User.objects.filter(id=user.id)

    def get_permissions(self):
        """Allow anyone to create users (registration), require auth for other actions."""
        if self.action == "create":
            return [OpenSignupAllowed()]
        return [IsAuthenticated()]

    def permission_denied(self, request, message=None, code=None):
        """Un refus d'inscription se dit en 403, jamais en 401.

        DRF convertit tout refus de permission en **401** dès que la requête
        n'est pas authentifiée et qu'un authenticator annonce un
        `WWW-Authenticate` — ce que fait `JWTAuthentication`, montée en premier.
        Or 401 veut dire « identifie-toi et recommence », et c'est faux ici :
        aucune paire d'identifiants n'ouvrira une inscription que l'instance a
        fermée. Un client qui suit le code irait boucler sur une page de
        connexion pour un compte qu'il n'a pas encore.
        """
        if self.action == "create":
            raise PermissionDenied(detail=message, code=code)
        return super().permission_denied(request, message=message, code=code)

    def get_throttles(self):
        """L'inscription est le seul geste anonyme qui *écrit*. Elle a son cap.

        Le plancher global (`core.throttles`) ne suffirait pas : il compte par IP
        toutes portées confondues, alors que ce qu'on veut borner ici est précis
        — le nombre de comptes qu'une même origine peut faire naître.
        """
        if self.action == "create":
            return [SignupRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """Return or update the current authenticated user."""
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        # PATCH — a user may only edit their own presentation and preferences,
        # never `is_staff` & co. The list lives on the serializer, next to the
        # validators that police those same fields: kept here, it drifted, and
        # `recap_disabled_chapters` was missing for as long as the recap page
        # had been sending it. Anything not listed is dropped in silence, so a
        # forgotten entry looks exactly like a saved preference that resets.
        data = {
            k: v for k, v in request.data.items()
            if k in UserSerializer.SELF_EDITABLE_FIELDS
        }
        serializer = self.get_serializer(
            request.user, data=data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        url_path='me/change-password',
        url_name='change-password',
        throttle_classes=[ChangePasswordRateThrottle],
    )
    def change_password(self, request):
        """Change the current user's password.

        POST /api/accounts/users/me/change-password/
        Body: { new_password, confirm_password }
        """
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')

        if not new_password or not confirm_password:
            return Response(
                {'detail': _('new_password and confirm_password are required.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {'detail': _('Password must be at least 8 characters.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {'detail': _('Passwords do not match.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=request.user)
        except ValidationError as exc:
            return Response(
                {'detail': ' '.join(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(new_password)
        request.user.save(update_fields=['password'])
        return Response({'detail': _('Password updated successfully.')}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='impersonate', permission_classes=[IsAdminUser])
    def impersonate(self, request, pk=None):
        """Generate a short-lived impersonation token for the target user.

        POST /api/accounts/users/{id}/impersonate/
        Only accessible to staff users.
        """
        target = self.get_object()
        if target == request.user:
            return Response(
                {'detail': _('You cannot impersonate yourself.')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tokens = get_impersonation_token(request.user, target)
        logger.info(
            "Impersonation: admin=%s (id=%s) impersonating user=%s (id=%s)",
            request.user.email, request.user.id,
            target.email, target.id,
        )
        return Response(tokens, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['post', 'delete'],
        url_path='me/avatar',
        url_name='avatar',
        parser_classes=[MultiPartParser, FormParser],
    )
    def avatar(self, request):
        """Upload or delete the current user's avatar image.

        POST  /api/accounts/users/me/avatar/  — upload (multipart, field: avatar)
        DELETE /api/accounts/users/me/avatar/ — remove
        """
        if request.method == 'DELETE':
            if not request.user.avatar:
                return Response(
                    {'detail': _('No avatar to delete.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Delete the file from storage
            old_path = request.user.avatar
            request.user.avatar = None
            request.user.save(update_fields=['avatar'])
            try:
                if old_path and hasattr(old_path, 'path') and os.path.isfile(old_path.path):
                    os.remove(old_path.path)
            except OSError:
                pass
            return Response({'detail': _('Avatar removed.')}, status=status.HTTP_200_OK)

        # POST — upload
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            return Response(
                {'avatar': [_('No file was submitted.')]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validate_upload(avatar_file, allowed_types=ALLOWED_IMAGE_TYPES, max_size=AVATAR_MAX_SIZE, field_name='avatar')

        # Delete old avatar if exists
        if request.user.avatar:
            try:
                old_path = request.user.avatar.path
                if os.path.isfile(old_path):
                    os.remove(old_path)
            except OSError:
                pass

        request.user.avatar = avatar_file
        request.user.save(update_fields=['avatar'])

        avatar_url = request.user.avatar.url if request.user.avatar else ''
        return Response({'avatar_url': avatar_url}, status=status.HTTP_200_OK)


class TokenObtainPairWithSessionView(TokenObtainPairView):
    """JWT login that also opens a Django session.

    Le SPA s'authentifie via `Authorization: Bearer <jwt>`, mais les requêtes
    `<img src=...>` et `<a href=...>` vers `/media/...` partent sans ce header
    (le navigateur n'envoie automatiquement que les cookies). Sans session,
    `serve_protected_media` voit AnonymousUser → 401.

    Poser un cookie sessionid au moment du login JWT permet aux requêtes
    natives de transporter l'auth. Les appels API gardent leur Bearer header.
    """

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])
        auth_login(
            request,
            serializer.user,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class TokenRefreshWithSessionView(TokenRefreshView):
    """Le refresh JWT est le battement de cœur de la session.

    ⚠️ **La session qui authentifie les images n'a pas le droit d'expirer avant
    le jeton qui maintient le SPA connecté.** Ouverte au seul login par la vue
    ci-dessus, elle vivait 14 jours fixes ; le refresh, lui, tourne 30 jours et
    **avec rotation**, donc indéfiniment tant que le foyer se sert de l'app —
    854 refresh pour 10 logins, mesurés en production.

    Au 14e jour, la session mourait sans que rien ne le dise : l'API répondait
    toujours, et **toutes** les images tombaient en 401 d'un coup — vignettes,
    photos, avatars. Deux horloges pour une seule connexion, et c'est la plus
    courte qui décidait, en silence (issue #567).

    D'où : tout refresh réussi prolonge la session, et **la rouvre si elle est
    déjà morte** — sans quoi un foyer déjà cassé le resterait jusqu'à ce que
    quelqu'un devine que se reconnecter répare.
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            self._renew_session(request, response.data)
        return response

    def _renew_session(self, request, data):
        user = self._user_of(data.get('refresh') or request.data.get('refresh'))
        if user is None:
            return

        if self._session_already_holds(request, user):
            # Session vivante, et déjà la bonne : on repousse seulement
            # l'échéance. Un `auth_login` ferait tourner le jeton CSRF à chaque
            # refresh — soit tous les quarts d'heure, sous les pieds d'un
            # éventuel appel authentifié par session.
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            auth_login(
                request,
                user,
                backend='django.contrib.auth.backends.ModelBackend',
            )

    @staticmethod
    def _session_already_holds(request, user):
        """La session porte-t-elle déjà *cet* utilisateur ?

        La comparaison passe par le champ de clé primaire, comme le fait
        ``django.contrib.auth._get_user_session_key`` : la session stocke une
        chaîne, et comparer des chaînes marcherait tant que la clé est un
        entier pour se mettre à mentir le jour où elle devient un UUID.
        """
        stored = request.session.get(SESSION_KEY)
        if stored is None:
            return False
        try:
            return User._meta.pk.to_python(stored) == user.pk
        except (ValueError, TypeError, ValidationError):
            return False

    @staticmethod
    def _user_of(raw_token):
        """L'utilisateur que désigne un refresh token, ou ``None``.

        Le jeton vient d'être validé par le serializer ; on le relit seulement
        pour savoir *qui* rafraîchit. Un échec ici ne doit jamais transformer
        un refresh réussi en erreur : au pire la session n'est pas prolongée,
        ce qui est exactement l'état d'avant.
        """
        if not raw_token:
            return None
        try:
            claims = RefreshToken(raw_token)
        except TokenError:
            return None
        user_id = claims.get(jwt_settings.USER_ID_CLAIM)
        if user_id is None:
            return None
        return User.objects.filter(**{jwt_settings.USER_ID_FIELD: user_id}).first()


@api_view(['GET'])
@permission_classes([AllowAny])
def signup_availability_view(request):
    """``GET /api/accounts/signup-availability/`` — l'inscription est-elle ouverte ?

    **Public à dessein, et c'est le seul endpoint des comptes qui le soit en
    lecture.** L'écran de connexion doit savoir s'il peut proposer « créer un
    compte » *avant* que quiconque soit authentifié — sinon on retombe sur le
    défaut que le parcours 28 a passé un lot entier à supprimer : une interface
    qui promet, et un clic qui dément. Une capacité indisponible se déclare.

    Ce qu'elle expose ne dit rien que la première tentative d'inscription ne
    dirait déjà, en 403 : le booléen ne cartographie rien, contrairement à
    `/api/capabilities/`, qui reste authentifié pour cette raison précise.
    """
    return Response(
        {"open": bool(getattr(settings, "ALLOW_OPEN_SIGNUP", True))},
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Lightweight me endpoint for SPA auth context.

    Écrit à la main plutôt que via `UserSerializer` — donc rien ne signale
    qu'un champ manque, et un champ manquant arrive `undefined` au front sans
    la moindre erreur. Toute clé ajoutée ici doit l'être dans `AuthUser`
    (`ui/src/lib/auth/authContext.ts`), et réciproquement : c'est ce que tient
    `tests/test_me_contract.py`.
    """
    user = request.user
    avatar_url = None
    if user.avatar:
        avatar_url = request.build_absolute_uri(user.avatar.url)
    return Response({
        'id': str(user.id),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'display_name': user.display_name,
        # Le nom d'affichage canonique, calculé par le modèle. Le front le lit
        # tel quel : recomposer la règle là-bas l'avait amputée (#546).
        'full_name': user.full_name,
        'active_household': str(user.active_household_id) if user.active_household_id else None,
        'is_staff': user.is_staff,
        'locale': user.locale or '',
        'avatar': avatar_url,
    })
