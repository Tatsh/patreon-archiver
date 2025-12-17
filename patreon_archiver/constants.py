"""Constants."""

from __future__ import annotations

__all__ = (
    'FIELDS',
    'MEDIA_URI',
    'PATREON_API_URI',
    'POSTS_URI',
    'SHARED_HEADERS',
    'SHARED_PARAMS',
    'USER_AGENT',
)

PATREON_API_URI = 'https://www.patreon.com/api'
MEDIA_URI = f'{PATREON_API_URI}/media'
POSTS_URI = f'{PATREON_API_URI}/posts'
USER_AGENT = 'Patreon/7.6.28 (Android; Android 11; Scale/2.10)'
SHARED_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en,en-GB;q=0.9,en-US;q=0.8',
    'authority': 'www.patreon.com',
    'cache-control': 'no-cache',
    'content-type': 'application/vnd.api+json',
    'dnt': '1',
    'pragma': 'no-cache',
    'referer': 'https://www.patreon.com/home',
    'user-agent': USER_AGENT,
}
FIELDS = {
    'campaign': (
        'avatar_photo_url,currency,earnings_visibility,is_monthly,is_nsfw,name,'
        'show_audio_post_download_links,url'
    ),
    'post': (
        'change_visibility_at,comment_count,content,current_user_can_comment,'
        'current_user_can_delete,current_user_can_view,current_user_has_liked,embed,'
        'has_ti_violation,image,is_paid,like_count,meta_image_url,min_cents_pledged_to_view,'
        'patreon_url,pledge_url,post_file,post_metadata,post_type,published_at,teaser_text,'
        'thumbnail_url,title,upgrade_url,url,was_posted_by_campaign_owner'
    ),
    'post_tag': 'tag_type,value',
    'user': 'image_url,full_name,url',
    'access_rule': 'access_rule_type,amount_cents',
    'media': 'download_url,file_name,id,image_urls,metadata',
    'contains_exclusive_posts': 'true',
    'is_draft': 'false',
}
SHARED_PARAMS = {
    'include': (
        'access_rules,attachments,audio,campaign,images,media,poll.choices,'
        'poll.current_user_responses.choice,poll.current_user_responses.poll,'
        'poll.current_user_responses.user,ti_checks,user,user_defined_tags'
    ),
    'sort': '-published_at',
    'json-api-version': '1.0',
    **{f'fields[{x}]': y for x, y in FIELDS.items()},
}

MEDIA_POST_TYPES = {'audio_file', 'audio_embed', 'video_embed', 'video_external_file'}
