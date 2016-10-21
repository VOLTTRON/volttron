'use strict';

var browserify = require('browserify');
var buffer = require('gulp-buffer');
var del = require('del');
var fs = require('fs');
var gulp = require('gulp');
var inject = require('gulp-inject');
var rev = require('gulp-rev');
var concat = require('gulp-concat');
var source = require('vinyl-source-stream');
var through2 = require('through2');

var BUILD_DIR = 'volttroncentral/webroot/';
var APP_GLOB = '{css,fonts,js}/app-*';
var VENDOR_GLOB = '{css,js}/{normalize,vendor}-*';

gulp.task('default', ['watch']);
gulp.task('clean-app', cleanApp);
gulp.task('clean-vendor', cleanVendor);
gulp.task('css', ['clean-app'], css);
gulp.task('fonts', ['clean-app'], fonts);
gulp.task('build', ['css', 'fonts', 'js', 'vendor'], htmlInject);
gulp.task('build-app', ['css', 'fonts', 'js'], htmlInject);
gulp.task('js', ['clean-app'], js);
gulp.task('watch', ['build'], watch);
gulp.task('vendor', ['clean-vendor'], vendor);

function cleanApp (callback) {
    del(BUILD_DIR + APP_GLOB, callback);
}

function cleanVendor(callback) {
    del(BUILD_DIR + VENDOR_GLOB, callback);
}

function css() {
    return gulp.src('ui-src/css/*.css')
        .pipe(concat('app.css'))
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'css'));
}

function fonts() {
    return gulp.src('ui-src/fonts/*')
        .pipe(gulp.dest(BUILD_DIR + 'fonts'));
}

function htmlInject() {
    return gulp.src('ui-src/index.html')
        .pipe(inject(gulp.src([VENDOR_GLOB, APP_GLOB], { cwd: BUILD_DIR}), { addRootSlash: false }))
        .pipe(gulp.dest(BUILD_DIR));
}

function js() {
    return browserify({
        bundleExternal: false,
        entries: './ui-src/js/app',
        extensions: ['.jsx'],
        transform: ['babelify'],
    })
        .bundle()
        .pipe(source('app.js'))
        .pipe(buffer())
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'js'));
}

function vendor() {
    gulp.src('node_modules/normalize.css/normalize.css')
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'css'));

    return browserify({
        noParse: [
            'bluebird/js/browser/bluebird.min',
            'd3/d3',
            'events',
            'jquery/dist/jquery.min',
            'moment/min/moment.min.js',
            'node-uuid',
            'react-addons-pure-render-mixin',
            'react-addons-shallow-compare',
            'react-click-outside',
            'nvd3/build/nv.d3.min',
            'keymirror',
            'react/dist/react',
            'react-dom/dist/react-dom',
            'react-router/umd/ReactRouter',
            'react-virtualized/dist/umd/react-virtualized',
            'history/umd/history',
            'immutable/dist/immutable',
            'react-select-me/lib/ReactSelectMe.js',
        ],
    })
        .require([
            { file: 'bluebird/js/browser/bluebird.min', expose: 'bluebird' },
            { file: 'babyparse/babyparse.js', expose: 'babyparse' },
            { file: 'd3/d3', expose: 'd3' },
            'events',
            'flux',
            { file: 'jquery/dist/jquery.min', expose: 'jquery' },
            { file: 'moment/min/moment.min.js', expose: 'moment' },
            'node-uuid',
            'react-addons-pure-render-mixin',
            'react-addons-shallow-compare',
            'react-click-outside',
            { file: 'nvd3/build/nv.d3.min', expose: 'nvd3' },
            'keymirror',
            { file: 'react/dist/react', expose: 'react' },
            { file: 'react-dom/dist/react-dom', expose: 'react-dom' },
            { file: 'react-virtualized/dist/umd/react-virtualized', expose: 'react-virtualized' },
            { file: 'react-router/umd/ReactRouter', expose: 'react-router' },
            { file: 'history/umd/history', expose: 'history' },
            { file: 'immutable/dist/immutable', expose: 'immutable' },
            { file: 'react-select-me/lib/ReactSelectMe.js', expose: 'react-select-me' },
        ])
        .transform(function (file) {
            if (file.match('/d3/d3.')) {
                var stream = through2();

                stream.push(new Buffer('/*\n'));
                stream.push(fs.readFileSync('node_modules/d3/LICENSE'));
                stream.push(new Buffer('*/\n'));

                return stream;
            }

            return through2();
        }, { global: true })
        .bundle()
        .pipe(source('vendor.js'))
        .pipe(buffer())
        .pipe(rev())
        .pipe(gulp.dest(BUILD_DIR + 'js'));
}

function watch() {
    return gulp.watch(['ui-src/**/*'], ['build-app']);
}