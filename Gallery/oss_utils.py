# Gallery/oss_utils.py
import oss2
from flask import current_app

def _get_bucket():
    ak       = current_app.config['OSS_ACCESS_KEY_ID']
    sk       = current_app.config['OSS_ACCESS_KEY_SECRET']
    endpoint = current_app.config['OSS_ENDPOINT']        # e.g. 'benjaling-1974819625145002.oss-cn-shanghai-internal.oss-accesspoint.aliyuncs.com'
    bucket   = current_app.config['OSS_BUCKET_NAME']     # 'benjaling'

    # 确保所有凭证和配置信息已填
    if not all([ak, sk, endpoint, bucket]):
        raise RuntimeError('Missing OSS config')

    auth = oss2.Auth(ak, sk)
    # 关键：启用 is_cname 模式
    return oss2.Bucket(auth, endpoint, bucket, is_cname=True)

def list_albums(prefix: str = '') -> list[str]:
    """
    列举指定前缀下的“相册”——使用 delimiter 分组得到的公共前缀列表
    """
    bucket = _get_bucket()
    # 使用 list_objects 接口的 delimiter 参数模拟目录
    result = bucket.list_objects(prefix=prefix, delimiter='/', max_keys=1000)
    # OSS SDK 在返回值中通过 prefix_list 提供公共前缀
    return result.prefix_list  # e.g. ['album1/', 'album2/']


def list_objects(prefix: str = '', marker: str = None, max_keys: int = 100) -> tuple[list[str], str]:
    """
    列举指定前缀下的对象 key 列表，支持分页。
    返回 (keys, next_marker)
    """
    bucket = _get_bucket()
    iterator = oss2.ObjectIterator(bucket, prefix=prefix, marker=marker, max_keys=max_keys)
    keys = [obj.key for obj in iterator]
    return keys, iterator.next_marker


def delete_object(key: str):
    """
    删除指定 key 的对象。
    """
    bucket = _get_bucket()
    bucket.delete_object(key)


def generate_signed_url(key: str, expires: int = 3600) -> str:
    """
    生成带签名的 GET URL，有效期 expires 秒。
    """
    bucket = _get_bucket()
    return bucket.sign_url('GET', key, expires)

