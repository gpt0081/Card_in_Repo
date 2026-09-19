import {useEffect,useState} from 'react';
import {AuthSession,getAuthSession,githubLoginUrl,logout} from './api';

export default function AuthStatus(){
  const [session,setSession]=useState<AuthSession>();
  const [error,setError]=useState(false);
  useEffect(()=>{let active=true;getAuthSession().then(value=>{if(active)setSession(value)}).catch(()=>{if(active)setError(true)});return()=>{active=false}},[]);
  if(error)return <aside className="authStatus" aria-label="GitHub account"><small>Account status unavailable. Public repositories still work.</small></aside>;
  if(!session)return <aside className="authStatus" aria-label="GitHub account"><small>Checking account…</small></aside>;
  if(session.authenticated&&session.user)return <aside className="authStatus" aria-label="GitHub account"><span>{session.user.avatar_url&&<img src={session.user.avatar_url} alt=""/>}<strong>@{session.user.login}</strong></span><button type="button" onClick={async()=>{await logout();setSession({authenticated:false,login_available:true})}}>Sign out</button></aside>;
  return <aside className="authStatus" aria-label="GitHub account"><small>{session.login_available?'Sign in to keep learning progress.':'Public repository mode'}</small>{session.login_available&&<a href={githubLoginUrl()}>Sign in with GitHub</a>}</aside>;
}
