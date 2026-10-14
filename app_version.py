"""Public build metadata. Bump SOURCE_VERSION before tagging a web release."""
import os,re
SOURCE_VERSION='0.2.0-beta.3'

def release_info():
    desktop=bool(os.environ.get('SPROCKET_DESKTOP_TOKEN'))
    edition='desktop' if desktop else 'web' if os.environ.get('SPROCKET_WEB')=='1' else 'source'
    version=os.environ.get('SPROCKET_RELEASE_VERSION',SOURCE_VERSION)
    commit=os.environ.get('RENDER_GIT_COMMIT','')
    return dict(version=version,edition=edition,build=commit[:12] if re.fullmatch(r'[0-9a-fA-F]{40}',commit) else '')
