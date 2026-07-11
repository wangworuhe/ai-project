import { createApp } from 'vue'
import App from './App.vue'
import router from "./router";
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

createApp(App).use(router).use(ElementPlus).mount('#app')



// const app = createApp(App)
// app.use(router)
// app.use(ElementPlus)
// app.mount('#app')