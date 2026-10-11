"""
Views 2FA — فاز ۸.۳

جریان:
1. کاربر از پروفایل → /accounts/2fa/setup/ → QR + تایید
2. بعد از تایید → کدهای بازیابی نمایش داده می‌شه
3. لاگین: password → اگه 2FA فعاله → /accounts/2fa/verify/ → کد ۶ رقمی
"""
import io
import base64

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken


# ═══════════════════════════════════════════════════════════
# توابع کمکی
# ═══════════════════════════════════════════════════════════

def get_confirmed_totp(user):
    """دستگاه TOTP تاییدشده کاربر (یا None)"""
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def get_unconfirmed_totp(user):
    """دستگاه TOTP در حال راه‌اندازی"""
    return TOTPDevice.objects.filter(user=user, confirmed=False).first()


def has_2fa(user):
    return get_confirmed_totp(user) is not None


def generate_recovery_codes(user, count=None):
    """تولید کدهای بازیابی جدید — برمی‌گردونه لیست کدها"""
    if count is None:
        count = getattr(settings, 'TWO_FACTOR_RECOVERY_CODES_COUNT', 10)

    device, _ = StaticDevice.objects.get_or_create(
        user=user, name='recovery', defaults={'confirmed': True},
    )
    # پاک کردن کدهای قبلی
    device.token_set.all().delete()

    codes = []
    for _ in range(count):
        token = StaticToken.random_token()
        device.token_set.create(token=token)
        codes.append(token)
    return codes


def verify_recovery_code(user, code):
    """آیا این کد بازیابی معتبره؟ (اگه بله، مصرف می‌شه)"""
    device = StaticDevice.objects.filter(user=user, confirmed=True).first()
    if not device:
        return False
    token = device.token_set.filter(token=code.strip().lower()).first()
    if not token:
        return False
    token.delete()
    return True


# ═══════════════════════════════════════════════════════════
# Setup — فعال‌سازی 2FA
# ═══════════════════════════════════════════════════════════

@login_required
def twofa_setup(request):
    """فعال‌سازی 2FA — نمایش QR + تایید"""
    user = request.user

    # اگه قبلاً فعاله، برو به disable
    if has_2fa(user):
        return redirect('accounts:twofa_disable')

    # حذف دستگاه‌های تاییدنشده قبلی (برای شروع تازه)
    TOTPDevice.objects.filter(user=user, confirmed=False).delete()
    device = TOTPDevice.objects.create(user=user, name='default', confirmed=False)

    if request.method == 'POST':
        code = request.POST.get('code', '').strip().replace(' ', '')

        # کاربر می‌خواد QR جدید بگیره
        if 'regenerate' in request.POST:
            device.delete()
            return redirect('accounts:twofa_setup')

        if not code:
            messages.error(request, 'لطفاً کد ۶ رقمی را وارد کنید.')
        elif device.verify_token(code):
            device.confirmed = True
            device.save()
            # تولید کدهای بازیابی
            codes = generate_recovery_codes(user)
            request.session['2fa_new_recovery_codes'] = codes
            messages.success(request, '✅ 2FA با موفقیت فعال شد.')
            return redirect('accounts:twofa_recovery_codes')
        else:
            messages.error(request, '❌ کد وارد شده صحیح نیست. دوباره تلاش کنید.')

    config_url = device.config_url

    return render(request, 'accounts/2fa_setup.html', {
        'device': device,
        'config_url': config_url,
        'secret_key': device.key,
    })


@login_required
def twofa_recovery_codes(request):
    """نمایش کدهای بازیابی — فقط یک‌بار"""
    codes = request.session.pop('2fa_new_recovery_codes', None)
    if not codes:
        messages.info(request, 'برای مشاهده‌ی کدهای بازیابی، ابتدا 2FA را فعال کنید.')
        return redirect('accounts:twofa_setup')

    return render(request, 'accounts/2fa_recovery_codes.html', {
        'codes': codes,
    })


@login_required
def twofa_regenerate_recovery(request):
    """تولید مجدد کدهای بازیابی (اگه کاربر همه رو گم کرده)"""
    if not has_2fa(request.user):
        return redirect('accounts:twofa_setup')

    if request.method == 'POST':
        codes = generate_recovery_codes(request.user)
        request.session['2fa_new_recovery_codes'] = codes
        messages.success(request, 'کدهای بازیابی جدید ساخته شد. کدهای قبلی باطل شدند.')
        return redirect('accounts:twofa_recovery_codes')

    return render(request, 'accounts/2fa_regenerate_confirm.html')


# ═══════════════════════════════════════════════════════════
# Disable — غیرفعال‌سازی 2FA
# ═══════════════════════════════════════════════════════════

@login_required
def twofa_disable(request):
    """غیرفعال‌سازی 2FA — نیاز به تایید کد فعلی"""
    user = request.user
    device = get_confirmed_totp(user)

    if not device:
        messages.info(request, '2FA از قبل غیرفعال است.')
        return redirect('hr:my_profile')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()

        verified = device.verify_token(code) or verify_recovery_code(user, code)

        if verified:
            device.delete()
            StaticDevice.objects.filter(user=user, name='recovery').delete()
            messages.success(request, '✅ 2FA غیرفعال شد.')
            return redirect('hr:my_profile')
        else:
            messages.error(request, '❌ کد صحیح نیست.')

    return render(request, 'accounts/2fa_disable.html', {
        'device': device,
    })


# ═══════════════════════════════════════════════════════════
# Verify — تایید در زمان لاگین
# ═══════════════════════════════════════════════════════════

@require_http_methods(['GET', 'POST'])
def twofa_verify(request):
    """تایید کد 2FA بعد از ورود نام‌کاربری/رمز"""
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        return redirect('accounts:login')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        request.session.pop('2fa_user_id', None)
        return redirect('accounts:login')

    device = get_confirmed_totp(user)
    if not device:
        # عجیب — کاربر 2FA نداره ولی اینجاست. لاگین کن.
        auth_login(request, user)
        request.session.pop('2fa_user_id', None)
        return redirect('dashboard:home')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip().replace(' ', '')

        # چک TOTP
        if code and device.verify_token(code):
            return _complete_login(request, user)

        # چک کد بازیابی
        if code and verify_recovery_code(user, code):
            messages.warning(request, '⚠️ این کد بازیابی مصرف شد. لطفاً کدهای جدید بسازید.')
            return _complete_login(request, user)

        messages.error(request, '❌ کد وارد شده صحیح نیست.')

    return render(request, 'accounts/2fa_verify.html', {
        'username': user.username,
    })


def _complete_login(request, user):
    """اتمام ورود + پاک‌سازی session"""
    auth_login(request, user)
    next_url = request.session.pop('2fa_next', None)
    request.session.pop('2fa_user_id', None)
    return redirect(next_url or reverse('dashboard:home'))